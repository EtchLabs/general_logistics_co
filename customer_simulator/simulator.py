"""Synthetic customer traffic: register customers and place varied orders."""

from __future__ import annotations

import asyncio
import logging
import random
from decimal import Decimal
from typing import Any

import httpx

from cart import build_random_cart, random_shipping_total
from config import get_settings, random_customer_payload

logger = logging.getLogger(__name__)


class CustomerSimulator:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.api_gateway_url.rstrip("/")
        self._interval_range = settings.resolved_order_interval()
        self.orders_per_hour = settings.estimated_orders_per_hour()
        self.new_customer_pct = settings.simulator_new_customer_pct
        self._customers: list[dict[str, Any]] = []
        self._skus: list[str] = []
        self.orders_placed = 0
        self.registrations = 0
        self.total_revenue = Decimal("0")

    def _interval_seconds(self) -> float:
        lo, hi = self._interval_range
        return random.uniform(lo, hi)

    async def refresh_catalog(self, client: httpx.AsyncClient) -> None:
        response = await client.get(f"{self.base_url}/products")
        if response.status_code != 200:
            logger.warning("Could not load products: HTTP %s", response.status_code)
            return
        skus: list[str] = []
        for product in response.json():
            for variant in product.get("variants", []):
                sku = variant.get("sku")
                if sku:
                    skus.append(sku)
        self._skus = sorted(set(skus))
        logger.info("Loaded %d SKUs from catalog", len(self._skus))

    async def register_customer(self, client: httpx.AsyncClient) -> dict[str, Any] | None:
        payload = random_customer_payload()
        response = await client.post(
            f"{self.base_url}/customers/register",
            json={
                "email": payload["email"],
                "password": payload["password"],
                "first_name": payload["first_name"],
                "last_name": payload["last_name"],
                "phone": payload["phone"],
            },
        )
        if response.status_code not in {200, 201}:
            logger.warning("Registration failed for %s: HTTP %s", payload["email"], response.status_code)
            return None

        data = response.json()
        customer = data["customer"]
        customer_id = customer["id"]

        address_resp = await client.post(
            f"{self.base_url}/customers/{customer_id}/addresses",
            json=payload["address"],
        )
        if address_resp.status_code not in {200, 201}:
            logger.warning("Address creation failed for %s", customer_id)

        self.registrations += 1
        record = {
            "customer_id": customer_id,
            "email": payload["email"],
            "address": payload["address"],
        }
        self._customers.append(record)
        logger.info("Registered customer %s", payload["email"])
        return record

    async def _pick_customer(self, client: httpx.AsyncClient) -> dict[str, Any] | None:
        if not self._customers or random.randint(1, 100) <= self.new_customer_pct:
            customer = await self.register_customer(client)
            if customer is None and self._customers:
                return random.choice(self._customers)
            return customer
        return random.choice(self._customers)

    @staticmethod
    def _format_cart_summary(line_items: list[dict[str, Any]]) -> str:
        parts = [f"{line['sku']}×{line['quantity']}" for line in line_items]
        return ", ".join(parts[:4]) + ("…" if len(parts) > 4 else "")

    async def place_order(self, client: httpx.AsyncClient) -> bool:
        if not self._skus:
            await self.refresh_catalog(client)
        if not self._skus:
            logger.warning("No SKUs available; skipping order")
            return False

        customer = await self._pick_customer(client)
        if customer is None:
            return False

        line_items = build_random_cart(self._skus)
        address = customer["address"]

        order_payload = {
            "customer_id": customer["customer_id"],
            "line_items": line_items,
            "shipping_address": {
                "label": address.get("label", "Shipping"),
                "line1": address["line1"],
                "line2": address.get("line2"),
                "city": address["city"],
                "state": address["state"],
                "postal_code": address["postal_code"],
                "country": address.get("country", "US"),
            },
            "shipping_total": random_shipping_total(),
        }

        response = await client.post(f"{self.base_url}/orders", json=order_payload)
        if response.status_code not in {200, 201}:
            logger.warning(
                "Order failed for %s: HTTP %s %s",
                customer["email"],
                response.status_code,
                response.text[:200],
            )
            return False

        order = response.json()
        grand_total = Decimal(str(order.get("grand_total", "0")))
        self.total_revenue += grand_total
        self.orders_placed += 1

        logger.info(
            "Placed order %s — %d lines [%s] $%s (session total $%s)",
            str(order.get("id", "?"))[:8],
            len(line_items),
            self._format_cart_summary(line_items),
            grand_total,
            self.total_revenue.quantize(Decimal("0.01")),
        )
        return True

    async def _fetch_all_by_status(
        self, client: httpx.AsyncClient, status: str, page_size: int = 100
    ) -> list[dict]:
        """Page through all orders with the given status."""
        all_orders: list[dict] = []
        offset = 0
        while True:
            try:
                resp = await client.get(
                    f"{self.base_url}/orders",
                    params={"status": status, "offset": offset, "limit": page_size},
                    timeout=15.0,
                )
                if resp.status_code != 200:
                    break
                page = resp.json()
                all_orders.extend(page)
                if len(page) < page_size:
                    break
                offset += page_size
            except httpx.HTTPError as exc:
                logger.debug("fetch_all_by_status (%s) error at offset %d: %s", status, offset, exc)
                break
        return all_orders

    async def advance_orders(self, client: httpx.AsyncClient) -> None:
        """Advance all orders through the fulfillment pipeline, paging through the full backlog."""
        pipeline = [
            ("confirmed",      "in_fulfillment"),
            ("in_fulfillment", "shipped"),
            ("shipped",        "delivered"),
            ("delivered",      "closed"),
        ]
        for from_status, to_status in pipeline:
            orders = await self._fetch_all_by_status(client, from_status)
            if not orders:
                continue
            advanced = 0
            for order in orders:
                try:
                    await client.patch(
                        f"{self.base_url}/orders/{order['id']}/status",
                        json={"status": to_status},
                        timeout=10.0,
                    )
                    advanced += 1
                except httpx.HTTPError:
                    pass
            if advanced:
                logger.info("Advanced %d orders: %s → %s", advanced, from_status, to_status)

    async def run_loop(self, stop_event: asyncio.Event) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await self.refresh_catalog(client)
            cycle = 0
            while not stop_event.is_set():
                try:
                    await self.place_order(client)
                except httpx.HTTPError as exc:
                    logger.error("Order cycle error: %s", exc)
                # Advance the pipeline every 3rd order cycle
                if cycle % 3 == 0:
                    await self.advance_orders(client)
                cycle += 1
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self._interval_seconds())
                except TimeoutError:
                    pass

    def stats(self) -> dict[str, Any]:
        avg = Decimal("0")
        if self.orders_placed:
            avg = (self.total_revenue / self.orders_placed).quantize(Decimal("0.01"))
        projected_daily = float(avg) * self.orders_per_hour * 24
        lo, hi = self._interval_range
        return {
            "orders_placed": self.orders_placed,
            "registrations": self.registrations,
            "active_customers": len(self._customers),
            "catalog_skus": len(self._skus),
            "total_revenue": str(self.total_revenue.quantize(Decimal("0.01"))),
            "avg_order_value": str(avg),
            "orders_per_hour_target": round(self.orders_per_hour, 1),
            "order_interval_seconds": f"{lo:.0f}-{hi:.0f}",
            "projected_daily_revenue": round(projected_daily, 2),
        }
