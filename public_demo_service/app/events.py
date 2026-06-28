"""Real-time event hub: Redis pub/sub, order polling, WebSocket broadcast."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import WebSocket
from redis.asyncio import Redis

from app.config import get_settings
from app.topology import BUSINESS_FLOWS, MICROSERVICE_FLOWS, build_node_blurbs

logger = logging.getLogger(__name__)


class EventHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._activity: deque[dict[str, Any]] = deque(maxlen=get_settings().activity_history_limit)
        self._lock = asyncio.Lock()
        self._seen_orders: set[str] = set()
        self._orders_today = 0
        self._last_stats: dict[str, Any] = {}

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        await ws.send_json({"type": "history", "items": list(self._activity)})
        if self._last_stats:
            await ws.send_json({"type": "stats", **self._last_stats})

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, message: dict[str, Any]) -> None:
        async with self._lock:
            if message.get("type") == "activity":
                self._activity.appendleft(message)
            clients = list(self._clients)
        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    def _trim_seen(self) -> None:
        if len(self._seen_orders) > 4000:
            self._seen_orders = set(list(self._seen_orders)[-2000:])

    @staticmethod
    def _order_summary(order: dict[str, Any]) -> tuple[str, str]:
        lines = order.get("line_items") or []
        total = order.get("grand_total", "?")
        oid = str(order.get("id", ""))[:8]
        parts = [f"{li.get('sku', '?')}×{li.get('quantity', 1)}" for li in lines[:5]]
        if len(lines) > 5:
            parts.append(f"+{len(lines) - 5} more")
        items = ", ".join(parts) if parts else "—"
        title = f"Storefront sale — ${total}"
        detail = f"Order #{oid} · {len(lines)} line(s): {items}"
        return title, detail

    def _flows_for_status(self, status: str) -> tuple[str, list, list]:
        if status in {"confirmed", "pending"}:
            key = "order_created"
        elif status in {"in_fulfillment", "shipped"}:
            key = "order_fulfilled"
        else:
            key = "order_confirmed"
        return (
            key,
            BUSINESS_FLOWS.get(key, BUSINESS_FLOWS["order_created"]),
            MICROSERVICE_FLOWS.get(key, MICROSERVICE_FLOWS["order_created"]),
        )

    async def emit_order(self, order: dict[str, Any], *, source: str = "live") -> None:
        oid = str(order.get("id", ""))
        if not oid or oid in self._seen_orders:
            return
        self._seen_orders.add(oid)
        self._trim_seen()
        self._orders_today += 1

        ts = datetime.now(UTC).isoformat()
        title, detail = self._order_summary(order)
        status = str(order.get("status", "created"))
        event_key, business_flow, micro_flow = self._flows_for_status(status)
        total = str(order.get("grand_total", "?"))
        try:
            total_fmt = f"{float(total):,.2f}"
        except (TypeError, ValueError):
            total_fmt = total
        blurb_ctx = {"total": total_fmt, "oid": oid[:8], "po": "PO"}

        await self.broadcast(
            {
                "type": "activity",
                "time": ts,
                "category": "storefront",
                "title": title,
                "detail": detail,
                "highlight_node": "storefront",
            }
        )
        await self.broadcast(
            {
                "type": "flow",
                "view": "business",
                "event": event_key,
                "label": title,
                "steps": [{"from": a, "to": b} for a, b in business_flow],
                "pulse_node": "storefront",
                "node_blurbs": build_node_blurbs("business", event_key, blurb_ctx),
            }
        )
        await self.broadcast(
            {
                "type": "flow",
                "view": "microservices",
                "event": event_key,
                "label": title,
                "steps": [{"from": a, "to": b} for a, b in micro_flow],
                "pulse_node": "website",
                "node_blurbs": build_node_blurbs("microservices", event_key, blurb_ctx),
            }
        )
        logger.debug("Emitted order flow %s via %s", oid[:8], source)

    async def handle_redis_message(self, channel: str, payload: dict) -> None:
        order_id = payload.get("order_id")
        if not order_id:
            return
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.api_gateway_url.rstrip('/')}/orders/{order_id}")
                if response.status_code == 200:
                    await self.emit_order(response.json(), source=f"redis:{channel}")
                    return
        except httpx.HTTPError:
            logger.warning("Could not fetch order %s for demo", order_id)

        # Fallback minimal payload from Redis
        await self.emit_order(
            {
                "id": order_id,
                "grand_total": payload.get("grand_total", "?"),
                "status": payload.get("status", channel.split(".")[-1]),
                "line_items": [],
            },
            source=f"redis:{channel}",
        )

    async def emit_supplier_flow(self, po_number: str = "PO") -> None:
        ts = datetime.now(UTC).isoformat()
        label = f"Supplier shipment — {po_number}"
        await self.broadcast(
            {
                "type": "activity",
                "time": ts,
                "category": "supply",
                "title": label,
                "detail": "Inbound widgets restock the warehouse",
                "highlight_node": "suppliers",
            }
        )
        blurb_ctx = {"total": "—", "oid": "—", "po": po_number}
        await self.broadcast(
            {
                "type": "flow",
                "view": "business",
                "event": "supplier_restock",
                "label": label,
                "steps": [{"from": a, "to": b} for a, b in BUSINESS_FLOWS["supplier_restock"]],
                "pulse_node": "suppliers",
                "node_blurbs": build_node_blurbs("business", "supplier_restock", blurb_ctx),
            }
        )
        await self.broadcast(
            {
                "type": "flow",
                "view": "microservices",
                "event": "supplier_po",
                "label": label,
                "steps": [{"from": a, "to": b} for a, b in MICROSERVICE_FLOWS["supplier_po"]],
                "pulse_node": "supplier",
                "node_blurbs": build_node_blurbs("microservices", "supplier_po", blurb_ctx),
            }
        )

    async def refresh_stats(self) -> None:
        settings = get_settings()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                sales = await client.get(f"{settings.api_gateway_url.rstrip('/')}/reports/sales-summary")
                if sales.status_code == 200:
                    data = sales.json()
                    stats = {
                        "type": "stats",
                        "order_count": data.get("order_count", 0),
                        "total_revenue": str(data.get("total_revenue", "0")),
                        "avg_order_value": str(data.get("average_order_value", "0")),
                        "session_orders": self._orders_today,
                    }
                    self._last_stats = stats
                    await self.broadcast(stats)
        except httpx.HTTPError:
            pass

    async def redis_listener(self, stop_event: asyncio.Event) -> None:
        settings = get_settings()
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.psubscribe(settings.redis_channel_pattern)
        logger.info("Public demo subscribed to %s", settings.redis_channel_pattern)
        try:
            async for message in pubsub.listen():
                if stop_event.is_set():
                    break
                if message["type"] != "pmessage":
                    continue
                channel = message["channel"]
                raw = message["data"]
                try:
                    payload = json.loads(raw) if isinstance(raw, str) else raw
                except json.JSONDecodeError:
                    payload = {"raw": raw}
                try:
                    await self.handle_redis_message(channel, payload)
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to handle redis message")
        finally:
            await pubsub.punsubscribe(settings.redis_channel_pattern)
            await pubsub.aclose()
            await redis.aclose()

    async def poll_orders_loop(self, stop_event: asyncio.Event) -> None:
        """Backup poller — catches orders with full line-item detail."""
        settings = get_settings()
        gateway = settings.api_gateway_url.rstrip("/")
        while not stop_event.is_set():
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    response = await client.get(f"{gateway}/orders")
                    if response.status_code == 200:
                        for order in response.json()[:30]:
                            await self.emit_order(order, source="poll")
            except httpx.HTTPError as exc:
                logger.debug("Order poll failed: %s", exc)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=2.5)
            except TimeoutError:
                pass

    async def poll_extras_loop(self, stop_event: asyncio.Event) -> None:
        """Periodic stats refresh and supplier visual pulses."""
        settings = get_settings()
        gateway = settings.api_gateway_url.rstrip("/")
        tick = 0
        while not stop_event.is_set():
            tick += 1
            await self.refresh_stats()
            if tick % 8 == 0:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        pos = await client.get(f"{gateway}/purchase-orders", params={"status": "submitted"})
                        if pos.status_code == 200 and pos.json():
                            po = pos.json()[0]
                            await self.emit_supplier_flow(po.get("po_number", "PO"))
                        else:
                            await self.emit_supplier_flow()
                except httpx.HTTPError:
                    await self.emit_supplier_flow()
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=15.0)
            except TimeoutError:
                pass


event_hub = EventHub()
