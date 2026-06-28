"""Seed the product catalog via the API gateway if empty."""

from __future__ import annotations

import asyncio
import logging
import sys

import httpx

from config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

CATEGORIES = [
    {"name": "Classic Widgets", "slug": "classic-widgets", "description": "Everyday widgets for home and office."},
    {"name": "Premium Widgets", "slug": "premium-widgets", "description": "High-end widgets with enhanced finishes."},
    {"name": "Industrial Widgets", "slug": "industrial-widgets", "description": "Heavy-duty widgets for commercial use."},
]

# Twelve distinct widget products — one primary SKU each for straightforward storefront browsing.
PRODUCTS = [
    {
        "name": "Standard Round Widget",
        "slug": "standard-round-widget",
        "description": "A dependable round widget for general-purpose applications.",
        "category_slug": "classic-widgets",
        "variants": [{"sku": "WDG-001", "attributes": {"size": "medium", "color": "silver"}}],
        "pricing": {"WDG-001": {"msrp": "9.99", "cost_basis": "4.50", "reorder_threshold": 200}},
    },
    {
        "name": "Mini Round Widget",
        "slug": "mini-round-widget",
        "description": "Compact round widget ideal for tight spaces and starter kits.",
        "category_slug": "classic-widgets",
        "variants": [{"sku": "WDG-002", "attributes": {"size": "small", "color": "silver"}}],
        "pricing": {"WDG-002": {"msrp": "6.99", "cost_basis": "3.00", "reorder_threshold": 250}},
    },
    {
        "name": "Jumbo Round Widget",
        "slug": "jumbo-round-widget",
        "description": "Oversized round widget for heavy-duty household projects.",
        "category_slug": "classic-widgets",
        "variants": [{"sku": "WDG-003", "attributes": {"size": "large", "color": "silver"}}],
        "pricing": {"WDG-003": {"msrp": "14.99", "cost_basis": "6.75", "reorder_threshold": 200}},
    },
    {
        "name": "Eco Bamboo Widget",
        "slug": "eco-bamboo-widget",
        "description": "Sustainably sourced bamboo widget with a warm natural finish.",
        "category_slug": "classic-widgets",
        "variants": [{"sku": "WDG-004", "attributes": {"material": "bamboo", "color": "natural"}}],
        "pricing": {"WDG-004": {"msrp": "11.99", "cost_basis": "5.25", "reorder_threshold": 220}},
    },
    {
        "name": "Modular Stack Widget",
        "slug": "modular-stack-widget",
        "description": "Interlocking stackable widget — build taller assemblies with ease.",
        "category_slug": "classic-widgets",
        "variants": [{"sku": "WDG-005", "attributes": {"type": "stackable", "color": "gray"}}],
        "pricing": {"WDG-005": {"msrp": "12.49", "cost_basis": "5.50", "reorder_threshold": 200}},
    },
    {
        "name": "Deluxe Hex Widget (Black)",
        "slug": "deluxe-hex-widget-black",
        "description": "Precision-machined hex widget with matte black alloy finish.",
        "category_slug": "premium-widgets",
        "variants": [{"sku": "WDG-006", "attributes": {"shape": "hex", "color": "black"}}],
        "pricing": {"WDG-006": {"msrp": "34.99", "cost_basis": "15.00", "reorder_threshold": 180}},
    },
    {
        "name": "Deluxe Hex Widget (Gold)",
        "slug": "deluxe-hex-widget-gold",
        "description": "Premium hex widget plated in brushed gold for a refined look.",
        "category_slug": "premium-widgets",
        "variants": [{"sku": "WDG-007", "attributes": {"shape": "hex", "color": "gold"}}],
        "pricing": {"WDG-007": {"msrp": "44.99", "cost_basis": "19.50", "reorder_threshold": 150}},
    },
    {
        "name": "Crystal Prism Widget",
        "slug": "crystal-prism-widget",
        "description": "Faceted prism widget that refracts light beautifully on display shelves.",
        "category_slug": "premium-widgets",
        "variants": [{"sku": "WDG-008", "attributes": {"shape": "prism", "color": "clear"}}],
        "pricing": {"WDG-008": {"msrp": "39.99", "cost_basis": "17.00", "reorder_threshold": 160}},
    },
    {
        "name": "Glow LED Widget",
        "slug": "glow-led-widget",
        "description": "Premium widget with integrated soft-glow LED accent ring.",
        "category_slug": "premium-widgets",
        "variants": [{"sku": "WDG-009", "attributes": {"feature": "led", "color": "white"}}],
        "pricing": {"WDG-009": {"msrp": "49.99", "cost_basis": "22.00", "reorder_threshold": 140}},
    },
    {
        "name": "Industrial Plate Widget (10in)",
        "slug": "industrial-plate-widget-10",
        "description": "Reinforced steel plate widget rated for high-load environments.",
        "category_slug": "industrial-widgets",
        "variants": [{"sku": "WDG-010", "attributes": {"size": "10in", "material": "steel"}}],
        "pricing": {"WDG-010": {"msrp": "59.99", "cost_basis": "28.00", "reorder_threshold": 120}},
    },
    {
        "name": "Industrial Plate Widget (12in)",
        "slug": "industrial-plate-widget-12",
        "description": "Extra-large steel plate widget for commercial installations.",
        "category_slug": "industrial-widgets",
        "variants": [{"sku": "WDG-011", "attributes": {"size": "12in", "material": "steel"}}],
        "pricing": {"WDG-011": {"msrp": "74.99", "cost_basis": "35.00", "reorder_threshold": 100}},
    },
    {
        "name": "Reinforced Torque Widget",
        "slug": "reinforced-torque-widget",
        "description": "Heavy-duty torque-rated widget built for factory floor demands.",
        "category_slug": "industrial-widgets",
        "variants": [{"sku": "WDG-012", "attributes": {"rating": "torque", "material": "steel"}}],
        "pricing": {"WDG-012": {"msrp": "89.99", "cost_basis": "42.00", "reorder_threshold": 100}},
    },
]


async def seed_catalog(base_url: str, *, force: bool = False) -> None:
    base_url = base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=30.0) as client:
        products_resp = await client.get(f"{base_url}/products")
        existing = products_resp.json() if products_resp.status_code == 200 else []
        existing_slugs = {p.get("slug") for p in existing}
        if len(existing_slugs) >= len(PRODUCTS) and not force:
            logger.info("Catalog already has %d products (target %d)", len(existing_slugs), len(PRODUCTS))
            return

        category_ids: dict[str, str] = {}
        for category in CATEGORIES:
            resp = await client.post(f"{base_url}/categories", json=category)
            if resp.status_code in {200, 201}:
                category_ids[category["slug"]] = resp.json()["id"]
                logger.info("Created category: %s", category["name"])
            elif resp.status_code == 409:
                listed = await client.get(f"{base_url}/categories")
                listed.raise_for_status()
                for item in listed.json():
                    category_ids[item["slug"]] = item["id"]
            else:
                resp.raise_for_status()

        for product in PRODUCTS:
            if product["slug"] in existing_slugs and not force:
                logger.info("Skipping existing product: %s", product["name"])
                continue
            payload = {
                "name": product["name"],
                "slug": product["slug"],
                "description": product["description"],
                "category_id": category_ids.get(product["category_slug"]),
                "images": [],
                "attributes": {},
                "variants": product["variants"],
            }
            resp = await client.post(f"{base_url}/products", json=payload)
            if resp.status_code in {200, 201}:
                logger.info("Created product: %s", product["name"])
            elif resp.status_code == 409:
                logger.info("Product already exists: %s", product["name"])
            else:
                resp.raise_for_status()

            for sku, pricing in product["pricing"].items():
                price_resp = await client.post(f"{base_url}/pricing/{sku}", json=pricing)
                if price_resp.status_code in {200, 201}:
                    logger.info("Created pricing for %s", sku)
                elif price_resp.status_code == 409:
                    logger.info("Pricing already exists for %s", sku)
                else:
                    price_resp.raise_for_status()


def main() -> int:
    settings = get_settings()
    try:
        asyncio.run(seed_catalog(settings.api_gateway_url))
        logger.info("Catalog seed complete.")
        return 0
    except httpx.HTTPError as exc:
        logger.error("Catalog seed failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
