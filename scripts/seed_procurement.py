#!/usr/bin/env python3
"""Seed procurement data: supplier links, reorder points, and invoice/receipt backfill."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8080").rstrip("/")

# Per-SKU reorder points (inventory per FC) and pricing thresholds.
SKU_REORDER_POINTS: dict[str, int] = {
    "WDG-001": 200,
    "WDG-002": 250,
    "WDG-003": 200,
    "WDG-004": 220,
    "WDG-005": 200,
    "WDG-006": 180,
    "WDG-007": 150,
    "WDG-008": 160,
    "WDG-009": 140,
    "WDG-010": 120,
    "WDG-011": 100,
    "WDG-012": 100,
}


async def get_json(client: httpx.AsyncClient, path: str) -> Any:
    response = await client.get(f"{API_GATEWAY_URL}{path}")
    if response.status_code != 200:
        return None
    return response.json()


async def seed_supplier_links(client: httpx.AsyncClient) -> str | None:
    suppliers = await get_json(client, "/suppliers")
    if not suppliers:
        logger.warning("No suppliers found — skipping supplier link seed")
        return None
    supplier_id = suppliers[0]["id"]
    logger.info("Linking SKUs to supplier %s", suppliers[0]["name"])

    products = await get_json(client, "/products") or []
    for product in products:
        for variant in product.get("variants", []):
            sku = variant.get("sku")
            if not sku:
                continue
            response = await client.patch(
                f"{API_GATEWAY_URL}/pricing/{sku}",
                json={"supplier_id": supplier_id, "reorder_threshold": SKU_REORDER_POINTS.get(sku, 200)},
            )
            if response.status_code == 200:
                logger.info("Linked pricing for %s", sku)
    return supplier_id


async def seed_reorder_points(client: httpx.AsyncClient) -> None:
    centers = await get_json(client, "/fulfillment-centers") or []
    products = await get_json(client, "/products") or []
    skus = [
        variant["sku"]
        for product in products
        for variant in product.get("variants", [])
        if variant.get("sku")
    ]
    for center in centers:
        fc_id = center["id"]
        for sku in skus:
            reorder_point = SKU_REORDER_POINTS.get(sku, 200)
            response = await client.patch(
                f"{API_GATEWAY_URL}/inventory/reorder-point",
                json={
                    "sku": sku,
                    "fulfillment_center_id": fc_id,
                    "reorder_point": reorder_point,
                },
            )
            if response.status_code == 200:
                logger.info("Set reorder point %s for %s @ %s", reorder_point, sku, center["code"])


async def reduce_stock_for_demo(client: httpx.AsyncClient) -> None:
    """Lower stock on a few SKUs so below-reorder-point returns results."""
    centers = await get_json(client, "/fulfillment-centers") or []
    if not centers:
        return
    fc = centers[0]
    demo_skus = list(SKU_REORDER_POINTS.keys())[:3]
    for sku in demo_skus:
        await client.post(
            f"{API_GATEWAY_URL}/inventory/adjust",
            json={
                "sku": sku,
                "fulfillment_center_id": fc["id"],
                "quantity_delta": -450,
                "movement_type": "adjust",
                "notes": "Procurement demo: simulate low stock",
            },
        )
        logger.info("Reduced stock for %s @ %s", sku, fc["code"])


async def backfill_receipts_and_invoices(client: httpx.AsyncClient) -> None:
    """Create receipts/invoices for POs that were shipped before receipt tracking existed."""
    pos = await get_json(client, "/purchase-orders") or []
    for po in pos:
        if po["status"] not in {"partially_received", "acknowledged", "received"}:
            continue
        po_id = po["id"]
        receipts = await get_json(client, f"/purchase-orders/{po_id}/receipts") or []
        if receipts:
            continue

        line_items = []
        for line in po.get("line_items", []):
            qty = line["quantity"]
            received = max(1, int(qty * 0.9))
            line_items.append({"sku": line["sku"], "quantity_shipped": received})

        response = await client.post(
            f"{API_GATEWAY_URL}/purchase-orders/{po_id}/shipments",
            json={
                "tracking_number": f"BACKFILL-{po['po_number']}",
                "shipped_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
                "line_items": line_items,
            },
        )
        if response.status_code in {200, 201, 204}:
            logger.info("Backfilled receipt/invoice for PO %s", po["po_number"])


async def run_seed() -> None:
    logger.info("Seeding procurement data via %s", API_GATEWAY_URL)
    async with httpx.AsyncClient(timeout=60.0) as client:
        health = await client.get(f"{API_GATEWAY_URL}/health")
        health.raise_for_status()
        await seed_supplier_links(client)
        await seed_reorder_points(client)
        await reduce_stock_for_demo(client)
        await backfill_receipts_and_invoices(client)
    logger.info("Procurement seed complete.")


def main() -> int:
    try:
        asyncio.run(run_seed())
        return 0
    except httpx.HTTPError as exc:
        logger.error("Procurement seed failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
