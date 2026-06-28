"""Synthetic supplier behavior: acknowledge and fulfill purchase orders."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from config import get_settings, simulate_shipment_behavior

logger = logging.getLogger(__name__)


class SupplierSimulator:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.api_gateway_url.rstrip("/")
        self.poll_interval = settings.supplier_poll_interval_seconds
        self.lead_time_min = settings.supplier_lead_time_days_min
        self.lead_time_max = settings.supplier_lead_time_days_max
        self.pos_acknowledged = 0
        self.pos_shipped = 0

    async def fetch_pending_pos(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        response = await client.get(
            f"{self.base_url}/purchase-orders",
            params={"status": "submitted"},
        )
        if response.status_code == 404:
            return []
        if response.status_code != 200:
            logger.warning("PO poll failed: HTTP %s", response.status_code)
            return []
        data = response.json()
        return data if isinstance(data, list) else data.get("items", [])

    async def acknowledge_po(self, client: httpx.AsyncClient, po: dict[str, Any]) -> bool:
        po_id = po.get("id") or po.get("purchase_order_id")
        if not po_id:
            return False

        behavior = simulate_shipment_behavior()
        lead_days = random.randint(self.lead_time_min, self.lead_time_max)
        payload = {
            "status": "acknowledged",
            "expected_delivery_date": (datetime.now(UTC) + timedelta(days=lead_days)).date().isoformat(),
            "notes": f"Simulated acknowledgement ({behavior['status']})",
        }
        response = await client.patch(
            f"{self.base_url}/purchase-orders/{po_id}",
            json=payload,
        )
        if response.status_code not in {200, 204}:
            logger.warning("PO acknowledge failed for %s: HTTP %s", po_id, response.status_code)
            return False

        self.pos_acknowledged += 1
        logger.info("Acknowledged PO %s (%s)", str(po_id)[:8], behavior["status"])
        return True

    async def ship_po(self, client: httpx.AsyncClient, po: dict[str, Any]) -> bool:
        po_id = po.get("id") or po.get("purchase_order_id")
        if not po_id:
            return False

        line_items = po.get("line_items", [])
        shipped_lines = []
        for line in line_items:
            qty = line.get("quantity", 0)
            shipped_qty = max(1, int(qty * random.uniform(0.95, 1.0)))
            shipped_lines.append({"sku": line.get("sku"), "quantity_shipped": shipped_qty})

        payload = {
            "tracking_number": f"SIM-{random.randint(100000, 999999)}",
            "shipped_at": datetime.now(UTC).isoformat(),
            "line_items": shipped_lines,
        }
        response = await client.post(
            f"{self.base_url}/purchase-orders/{po_id}/shipments",
            json=payload,
        )
        if response.status_code not in {200, 201, 204}:
            logger.debug("PO shipment skipped for %s: HTTP %s", po_id, response.status_code)
            return False

        self.pos_shipped += 1
        logger.info("Shipped PO %s", str(po_id)[:8])
        return True

    async def process_cycle(self, client: httpx.AsyncClient) -> None:
        pending = await self.fetch_pending_pos(client)
        if not pending:
            logger.debug("No pending purchase orders")
            return

        for po in pending:
            if await self.acknowledge_po(client, po):
                if random.random() < 0.7:
                    await self.ship_po(client, po)

    async def run_loop(self, stop_event: asyncio.Event) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            while not stop_event.is_set():
                try:
                    await self.process_cycle(client)
                except httpx.HTTPError as exc:
                    logger.error("Supplier cycle error: %s", exc)
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=float(self.poll_interval))
                except TimeoutError:
                    pass

    def stats(self) -> dict[str, int]:
        return {
            "pos_acknowledged": self.pos_acknowledged,
            "pos_shipped": self.pos_shipped,
        }
