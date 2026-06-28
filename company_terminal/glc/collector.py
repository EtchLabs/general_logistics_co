from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from glc.config import Settings, get_settings
from glc.registry import SERVICES, ServiceDef


@dataclass
class ServiceHealth:
    label: str
    port: int
    group: str
    status: str = "unknown"
    uptime: float | None = None
    version: str | None = None
    detail: str | None = None
    latency_ms: float | None = None


@dataclass
class Snapshot:
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    gateway_ok: bool = False
    services: list[ServiceHealth] = field(default_factory=list)
    orders: list[dict[str, Any]] = field(default_factory=list)
    order_count: int = 0
    sales: dict[str, Any] | None = None
    inventory_summary: dict[str, Any] | None = None
    income_statement: dict[str, Any] | None = None
    notifications: list[dict[str, Any]] = field(default_factory=list)
    notification_total: int = 0
    fulfillment_centers: list[dict[str, Any]] = field(default_factory=list)
    stock_levels: list[dict[str, Any]] = field(default_factory=list)
    suppliers: list[dict[str, Any]] = field(default_factory=list)
    purchase_orders: list[dict[str, Any]] = field(default_factory=list)
    tax_rates: list[dict[str, Any]] = field(default_factory=list)
    employees: list[dict[str, Any]] = field(default_factory=list)
    departments: list[dict[str, Any]] = field(default_factory=list)
    accounts: list[dict[str, Any]] = field(default_factory=list)
    shipping_quotes: list[dict[str, Any]] = field(default_factory=list)
    customer_sim: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)


class DataCollector:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def collect(self) -> Snapshot:
        snap = Snapshot()
        with httpx.Client(timeout=4.0) as client:
            snap.gateway_ok = self._ping(client, f"{self.settings.api_gateway_url}/health")
            snap.services = self._health_grid(client)
            if snap.gateway_ok:
                self._fetch_gateway_data(client, snap)
            self._fetch_simulator(client, snap)
        return snap

    def _ping(self, client: httpx.Client, url: str) -> bool:
        try:
            return client.get(url).status_code == 200
        except httpx.HTTPError:
            return False

    def _health_grid(self, client: httpx.Client) -> list[ServiceHealth]:
        results: list[ServiceHealth] = []
        host = self.settings.host
        for svc in SERVICES:
            health = ServiceHealth(label=svc.label, port=svc.port, group=svc.group)
            if svc.port == 0:
                health.status = "running"
                health.detail = "no health port"
                results.append(health)
                continue
            url = f"http://{host}:{svc.port}/health"
            started = time.perf_counter()
            try:
                resp = client.get(url)
                health.latency_ms = round((time.perf_counter() - started) * 1000, 1)
                if resp.status_code == 200:
                    body = resp.json()
                    health.status = body.get("status", "ok")
                    health.uptime = body.get("uptime_seconds")
                    health.version = body.get("version")
                    if body.get("dependencies"):
                        bad = [
                            k
                            for k, v in body["dependencies"].items()
                            if isinstance(v, dict) and v.get("status") != "ok"
                        ]
                        if bad:
                            health.detail = f"deps: {', '.join(bad)}"
                else:
                    health.status = "error"
                    health.detail = f"HTTP {resp.status_code}"
            except httpx.HTTPError as exc:
                health.status = "down"
                health.detail = str(exc)[:60]
            results.append(health)
        return results

    def _safe_get(self, client: httpx.Client, path: str) -> Any | None:
        try:
            resp = client.get(f"{self.settings.api_gateway_url}{path}")
            if resp.status_code == 200:
                return resp.json()
        except httpx.HTTPError:
            pass
        return None

    def _safe_post(self, client: httpx.Client, path: str, body: dict) -> Any | None:
        try:
            resp = client.post(f"{self.settings.api_gateway_url}{path}", json=body)
            if resp.status_code in {200, 201}:
                return resp.json()
        except httpx.HTTPError:
            pass
        return None

    def _fetch_gateway_data(self, client: httpx.Client, snap: Snapshot) -> None:
        gw = self.settings.api_gateway_url
        try:
            orders = client.get(f"{gw}/orders")
            if orders.status_code == 200:
                all_orders = orders.json()
                snap.order_count = len(all_orders)
                snap.orders = all_orders[:25]
        except httpx.HTTPError as exc:
            snap.errors.append(f"orders: {exc}")

        snap.sales = self._safe_get(client, "/reports/sales-summary")
        snap.inventory_summary = self._safe_get(client, "/reports/inventory-summary")
        snap.income_statement = self._safe_get(client, "/reports/income-statement")

        notif = self._safe_get(client, "/notifications?limit=30")
        if isinstance(notif, dict):
            snap.notifications = notif.get("notifications", [])
            snap.notification_total = notif.get("total", len(snap.notifications))

        snap.fulfillment_centers = self._safe_get(client, "/fulfillment-centers") or []
        snap.suppliers = self._safe_get(client, "/suppliers") or []
        snap.purchase_orders = self._safe_get(client, "/purchase-orders") or []
        snap.tax_rates = self._safe_get(client, "/tax/rates") or []
        snap.employees = self._safe_get(client, "/employees") or []
        snap.departments = self._safe_get(client, "/departments") or []
        snap.accounts = self._safe_get(client, "/accounts") or []

        products = self._safe_get(client, "/products") or []
        skus: list[str] = []
        for product in products[:8]:
            for variant in product.get("variants", []):
                sku = variant.get("sku")
                if sku:
                    skus.append(sku)
        for sku in skus[:12]:
            inv = self._safe_get(client, f"/inventory/{sku}")
            if inv:
                snap.stock_levels.append(inv)

        quotes = self._safe_post(
            client,
            "/shipping/rates",
            {
                "ship_to": {
                    "line1": "1 Harbor Blvd",
                    "city": "Oakland",
                    "state": "CA",
                    "postal_code": "94607",
                    "country": "US",
                },
                "weight_oz": "32",
                "origin_postal_code": "64129",
            },
        )
        if isinstance(quotes, dict):
            snap.shipping_quotes = quotes.get("quotes", [])

    def _fetch_simulator(self, client: httpx.Client, snap: Snapshot) -> None:
        try:
            resp = client.get(f"http://{self.settings.host}:8020/health")
            if resp.status_code == 200:
                snap.customer_sim = resp.json()
        except httpx.HTTPError:
            snap.customer_sim = None
