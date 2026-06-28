#!/usr/bin/env python3
"""Seed reference data across GLC microservices via the API gateway."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import date
from typing import Any

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://localhost:8080").rstrip("/")

FULFILLMENT_CENTERS = [
    {
        "code": "FC-WEST",
        "name": "Pacific Fulfillment Center",
        "line1": "1200 Harbor Blvd",
        "city": "Oakland",
        "state": "CA",
        "postal_code": "94607",
        "country": "US",
    },
    {
        "code": "FC-CENTRAL",
        "name": "Heartland Fulfillment Center",
        "line1": "4500 Logistics Pkwy",
        "city": "Kansas City",
        "state": "MO",
        "postal_code": "64129",
        "country": "US",
    },
    {
        "code": "FC-EAST",
        "name": "Atlantic Fulfillment Center",
        "line1": "800 Distribution Dr",
        "city": "Newark",
        "state": "NJ",
        "postal_code": "07114",
        "country": "US",
    },
]

SUPPLIERS = [
    {
        "name": "Acme Widget Supply Co.",
        "contact_email": "orders@acme-widgets.example.com",
        "lead_time_days": 5,
        "reliability_score": "92.00",
    },
    {
        "name": "Northern Alloy Widgets",
        "contact_email": "po@northalloy.example.com",
        "lead_time_days": 7,
        "reliability_score": "88.00",
    },
    {
        "name": "Pacific Precision Parts",
        "contact_email": "procurement@pacprecision.example.com",
        "lead_time_days": 4,
        "reliability_score": "95.00",
    },
]

DEPARTMENTS = [
    {"code": "OPS", "name": "Operations"},
    {"code": "FIN", "name": "Finance"},
    {"code": "HR", "name": "Human Resources"},
    {"code": "WH", "name": "Warehouse"},
    {"code": "CS", "name": "Customer Service"},
]

EMPLOYEES = [
    {
        "first_name": "Maria",
        "last_name": "Santos",
        "email": "maria.santos@glc.internal",
        "department_code": "OPS",
        "hire_date": "2022-01-15",
        "salary": "85000.00",
    },
    {
        "first_name": "James",
        "last_name": "Whitfield",
        "email": "james.whitfield@glc.internal",
        "department_code": "FIN",
        "hire_date": "2021-06-01",
        "salary": "92000.00",
    },
    {
        "first_name": "Priya",
        "last_name": "Sharma",
        "email": "priya.sharma@glc.internal",
        "department_code": "HR",
        "hire_date": "2020-03-10",
        "salary": "88000.00",
    },
    {
        "first_name": "David",
        "last_name": "Nguyen",
        "email": "david.nguyen@glc.internal",
        "department_code": "WH",
        "hire_date": "2023-02-20",
        "salary": "62000.00",
    },
    {
        "first_name": "Emily",
        "last_name": "Carter",
        "email": "emily.carter@glc.internal",
        "department_code": "CS",
        "hire_date": "2022-09-01",
        "salary": "58000.00",
    },
]

CHART_OF_ACCOUNTS = [
    {"code": "1000", "name": "Cash", "account_type": "asset"},
    {"code": "1100", "name": "Accounts Receivable", "account_type": "asset"},
    {"code": "1200", "name": "Inventory", "account_type": "asset"},
    {"code": "2000", "name": "Accounts Payable", "account_type": "liability"},
    {"code": "2100", "name": "Sales Tax Payable", "account_type": "liability"},
    {"code": "3000", "name": "Retained Earnings", "account_type": "equity"},
    {"code": "4000", "name": "Product Sales", "account_type": "revenue"},
    {"code": "5000", "name": "Cost of Goods Sold", "account_type": "expense"},
    {"code": "5200", "name": "Payroll Expense", "account_type": "expense"},
]

DEFAULT_STOCK_QTY = 500


async def post_or_skip(
    client: httpx.AsyncClient,
    path: str,
    payload: dict[str, Any],
    *,
    label: str,
) -> dict[str, Any] | None:
    response = await client.post(f"{API_GATEWAY_URL}{path}", json=payload)
    if response.status_code in {200, 201}:
        logger.info("Created %s", label)
        return response.json()
    if response.status_code == 409:
        logger.info("%s already exists", label)
        return None
    if response.status_code == 404:
        logger.warning("%s — service not available (404)", label)
        return None
    logger.warning("%s failed: HTTP %s %s", label, response.status_code, response.text[:200])
    return None


async def seed_fulfillment_centers(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    created: list[dict[str, Any]] = []
    for fc in FULFILLMENT_CENTERS:
        result = await post_or_skip(client, "/fulfillment-centers", fc, label=f"FC {fc['code']}")
        if result:
            created.append(result)
    return created


async def seed_suppliers(client: httpx.AsyncClient) -> None:
    for supplier in SUPPLIERS:
        await post_or_skip(client, "/suppliers", supplier, label=supplier["name"])


async def seed_departments(client: httpx.AsyncClient) -> dict[str, str]:
    dept_ids: dict[str, str] = {}
    for dept in DEPARTMENTS:
        result = await post_or_skip(client, "/departments", dept, label=f"department {dept['code']}")
        if result and result.get("id"):
            dept_ids[dept["code"]] = result["id"]
    listed = await client.get(f"{API_GATEWAY_URL}/departments")
    if listed.status_code == 200:
        for item in listed.json():
            dept_ids[item["code"]] = item["id"]
    return dept_ids


async def seed_employees(client: httpx.AsyncClient, dept_ids: dict[str, str]) -> None:
    for employee in EMPLOYEES:
        payload = {
            "first_name": employee["first_name"],
            "last_name": employee["last_name"],
            "email": employee["email"],
            "hire_date": employee["hire_date"],
            "department_id": dept_ids.get(employee["department_code"]),
            "salary": employee["salary"],
        }
        await post_or_skip(client, "/employees", payload, label=employee["email"])


async def seed_chart_of_accounts(client: httpx.AsyncClient) -> None:
    for account in CHART_OF_ACCOUNTS:
        await post_or_skip(client, "/accounts", account, label=f"account {account['code']}")


async def seed_inventory_stock(client: httpx.AsyncClient) -> None:
    fc_response = await client.get(f"{API_GATEWAY_URL}/fulfillment-centers")
    if fc_response.status_code != 200:
        logger.warning("Fulfillment centers unavailable — skipping stock seed")
        return
    centers = fc_response.json()

    products_response = await client.get(f"{API_GATEWAY_URL}/products")
    if products_response.status_code != 200:
        logger.warning("Product catalog unavailable — skipping stock seed")
        return

    skus: list[str] = []
    for product in products_response.json():
        for variant in product.get("variants", []):
            if variant.get("sku"):
                skus.append(variant["sku"])
    if not skus:
        return

    for center in centers:
        fc_id = center["id"]
        for sku in skus:
            await post_or_skip(
                client,
                "/inventory/adjust",
                {
                    "sku": sku,
                    "fulfillment_center_id": fc_id,
                    "quantity_delta": DEFAULT_STOCK_QTY,
                    "movement_type": "receive",
                    "notes": "Initial stock seed",
                },
                label=f"stock {sku} @ {center.get('code')}",
            )


async def run_seed() -> None:
    logger.info("Seeding GLC reference data via %s", API_GATEWAY_URL)
    async with httpx.AsyncClient(timeout=60.0) as client:
        health = await client.get(f"{API_GATEWAY_URL}/health")
        health.raise_for_status()
        await seed_fulfillment_centers(client)
        await seed_suppliers(client)
        dept_ids = await seed_departments(client)
        await seed_employees(client, dept_ids)
        await seed_chart_of_accounts(client)
        await seed_inventory_stock(client)
    logger.info("Seed complete.")


def main() -> int:
    try:
        asyncio.run(run_seed())
        return 0
    except httpx.HTTPError as exc:
        logger.error("Seed failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
