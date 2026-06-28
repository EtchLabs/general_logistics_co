import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from fastapi import HTTPException

from app.config import get_settings
from app.db.mongo import get_mongo_db
from app.db.redis import get_redis


async def ensure_mongo_indexes() -> None:
    db = get_mongo_db()
    await db.report_snapshots.create_index("report_type")
    await db.report_snapshots.create_index("generated_at")


async def _save_snapshot(report_type: str, data: dict) -> None:
    db = get_mongo_db()
    await db.report_snapshots.insert_one(
        {
            "report_type": report_type,
            "data": data,
            "generated_at": datetime.now(UTC),
        }
    )


async def get_sales_summary() -> dict:
    settings = get_settings()
    cache_key = "report:sales-summary"

    cached = await get_redis().get(cache_key)
    if cached:
        return json.loads(cached)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.order_service_url}/orders/stats")
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch order stats: {exc}") from exc

    order_count = data.get("total", 0)
    total_revenue = data.get("total_revenue", "0")
    average_order_value = data.get("avg_order_value", "0")

    result = {
        "order_count": order_count,
        "total_revenue": str(total_revenue),
        "average_order_value": str(average_order_value),
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "order_service",
    }

    # Short TTL so the live demo stats bar reflects real counts quickly.
    await get_redis().set(cache_key, json.dumps(result), ex=30)
    await _save_snapshot("sales-summary", result)
    return result


async def get_inventory_summary() -> dict:
    settings = get_settings()
    cache_key = "report:inventory-summary"

    cached = await get_redis().get(cache_key)
    if cached:
        return json.loads(cached)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.product_service_url}/products")
            response.raise_for_status()
            products = response.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch products: {exc}") from exc

    categories: dict[str, int] = {}
    active_products = 0
    for product in products:
        if product.get("is_active", True):
            active_products += 1
        category = product.get("category_name") or product.get("category") or "uncategorized"
        categories[category] = categories.get(category, 0) + 1

    result = {
        "product_count": len(products),
        "active_products": active_products,
        "categories": categories,
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "product_service",
    }

    await get_redis().set(cache_key, json.dumps(result), ex=settings.cache_ttl_seconds)
    await _save_snapshot("inventory-summary", result)
    return result
