import base64
import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import httpx
from fastapi import HTTPException
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.redis import get_redis
from app.models.postgres import (
    Order,
    OrderEvent,
    OrderLineItem,
    OrderStatus,
    PaymentStatus,
)

VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.IN_FULFILLMENT, OrderStatus.CANCELLED},
    OrderStatus.IN_FULFILLMENT: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: {OrderStatus.CLOSED},
    OrderStatus.CLOSED: set(),
    OrderStatus.CANCELLED: set(),
}


async def cache_get(key: str) -> str | None:
    return await get_redis().get(key)


async def cache_set(key: str, value: str) -> None:
    settings = get_settings()
    await get_redis().set(key, value, ex=settings.cache_ttl_seconds)


async def cache_delete(key: str) -> None:
    await get_redis().delete(key)


async def publish_event(channel: str, payload: dict) -> None:
    await get_redis().publish(channel, json.dumps(payload, default=str))


async def get_order_or_404(session: AsyncSession, order_id: UUID) -> Order:
    result = await session.execute(
        select(Order)
        .options(selectinload(Order.line_items), selectinload(Order.events))
        .where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


async def verify_customer(customer_id: UUID) -> None:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{settings.customer_service_url}/customers/{customer_id}")
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Customer not found")
        response.raise_for_status()


async def fetch_customer_id_by_email(email: str) -> UUID:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(
            f"{settings.customer_service_url}/customers/by-email/{email.lower()}"
        )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Customer not found")
        response.raise_for_status()
        return UUID(response.json()["id"])


def encode_order_cursor(created_at: datetime, order_id: UUID) -> str:
    raw = f"{created_at.isoformat()}|{order_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_order_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        created_at_str, order_id_str = raw.split("|", 1)
        return datetime.fromisoformat(created_at_str), UUID(order_id_str)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor") from exc


async def fetch_sku_price(sku: str, quantity: int, coupon_code: str | None) -> dict:
    settings = get_settings()
    params: dict = {"quantity": quantity}
    if coupon_code:
        params["coupon_code"] = coupon_code
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(
            f"{settings.product_service_url}/pricing/{sku}/calculate",
            params=params,
        )
        if response.status_code == 404:
            raise HTTPException(status_code=400, detail=f"SKU not found or not priced: {sku}")
        response.raise_for_status()
        return response.json()


async def fetch_product_name(sku: str) -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{settings.product_service_url}/products/sku/{sku}")
        if response.status_code == 404:
            raise HTTPException(status_code=400, detail=f"SKU not found in catalog: {sku}")
        response.raise_for_status()
        data = response.json()
        for variant in data.get("variants", []):
            if variant["sku"] == sku:
                attrs = ", ".join(f"{k}={v}" for k, v in variant.get("attributes", {}).items())
                return f"{data['name']} ({attrs})" if attrs else data["name"]
        return data["name"]


async def record_event(
    session: AsyncSession,
    order: Order,
    event_type: str,
    from_status: OrderStatus | None = None,
    to_status: OrderStatus | None = None,
    metadata: dict | None = None,
) -> OrderEvent:
    event = OrderEvent(
        order_id=order.id,
        event_type=event_type,
        from_status=from_status.value if from_status else None,
        to_status=to_status.value if to_status else None,
        details=metadata or {},
    )
    session.add(event)
    return event


def assert_transition(current: OrderStatus, target: OrderStatus) -> None:
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {current.value} to {target.value}",
        )


async def transition_order(
    session: AsyncSession,
    order: Order,
    target: OrderStatus,
    event_type: str,
    metadata: dict | None = None,
) -> Order:
    current = order.status
    assert_transition(current, target)
    order.status = target
    if target in {OrderStatus.CLOSED, OrderStatus.CANCELLED}:
        order.closed_at = datetime.now(UTC)
    if target == OrderStatus.CANCELLED:
        order.payment_status = PaymentStatus.REFUNDED
    await record_event(session, order, event_type, current, target, metadata)
    await session.commit()
    await session.refresh(order)
    await cache_delete(f"order:status:{order.id}")
    await publish_event(
        f"orders.{target.value}",
        {
            "order_id": str(order.id),
            "customer_id": str(order.customer_id),
            "status": target.value,
            "event_type": event_type,
        },
    )
    return order


async def calculate_order_totals(
    line_inputs: list,
    coupon_code: str | None,
    shipping_total: Decimal,
) -> tuple[list[dict], Decimal, Decimal]:
    settings = get_settings()
    computed_lines: list[dict] = []
    subtotal = Decimal("0")
    discount_total = Decimal("0")

    for item in line_inputs:
        price_data = await fetch_sku_price(item.sku, item.quantity, coupon_code)
        product_name = await fetch_product_name(item.sku)
        unit_price = Decimal(str(price_data["unit_price"]))
        line_total = Decimal(str(price_data["total"]))
        line_discount = Decimal(str(price_data["coupon_discount"]))
        discount_total += line_discount
        subtotal += line_total
        computed_lines.append(
            {
                "sku": item.sku,
                "product_name": product_name,
                "quantity": item.quantity,
                "unit_price": unit_price,
                "line_total": line_total,
            }
        )

    tax_total = (subtotal * Decimal(str(settings.tax_rate_percent)) / Decimal("100")).quantize(
        Decimal("0.01")
    )
    grand_total = subtotal + tax_total + shipping_total
    return computed_lines, tax_total, discount_total
