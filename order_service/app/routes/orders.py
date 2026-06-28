from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.postgres import get_session
from app.models.postgres import Order, OrderLineItem, OrderStatus, PaymentStatus
from app.models.schemas import (
    OrderCreate,
    OrderEventOut,
    OrderListOut,
    OrderOut,
    OrderStatusOut,
    OrderStatusUpdate,
    ReturnRequest,
)
from app.services.order_service import (
    calculate_order_totals,
    cache_get,
    cache_set,
    decode_order_cursor,
    encode_order_cursor,
    fetch_customer_id_by_email,
    get_order_or_404,
    publish_event,
    record_event,
    transition_order,
    verify_customer,
)

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=201)
async def create_order(
    payload: OrderCreate,
    session: AsyncSession = Depends(get_session),
) -> OrderOut:
    await verify_customer(payload.customer_id)

    lines, tax_total, discount_total = await calculate_order_totals(
        payload.line_items,
        payload.coupon_code,
        payload.shipping_total,
    )
    subtotal = sum((line["line_total"] for line in lines), Decimal("0"))
    grand_total = subtotal + tax_total + payload.shipping_total

    order = Order(
        customer_id=payload.customer_id,
        order_type=payload.order_type,
        status=OrderStatus.PENDING,
        payment_status=PaymentStatus.AUTHORIZED,
        subtotal=subtotal,
        tax_total=tax_total,
        shipping_total=payload.shipping_total,
        discount_total=discount_total,
        grand_total=grand_total,
        coupon_code=payload.coupon_code.upper() if payload.coupon_code else None,
        shipping_address=payload.shipping_address.model_dump(),
    )
    session.add(order)
    await session.flush()

    for line in lines:
        session.add(OrderLineItem(order_id=order.id, **line))

    await record_event(
        session,
        order,
        "order.created",
        None,
        OrderStatus.PENDING,
        {"line_count": len(lines), "grand_total": str(grand_total)},
    )
    await session.commit()

    order = await get_order_or_404(session, order.id)
    order.status = OrderStatus.CONFIRMED
    order.payment_status = PaymentStatus.CAPTURED
    await record_event(
        session,
        order,
        "order.confirmed",
        OrderStatus.PENDING,
        OrderStatus.CONFIRMED,
        {"payment": "mock_captured"},
    )
    await session.commit()

    await publish_event(
        "orders.created",
        {
            "order_id": str(order.id),
            "customer_id": str(order.customer_id),
            "grand_total": str(order.grand_total),
        },
    )

    order = await get_order_or_404(session, order.id)
    await cache_set(
        f"order:status:{order.id}",
        OrderStatusOut(
            order_id=order.id,
            status=order.status,
            payment_status=order.payment_status,
            updated_at=order.updated_at,
        ).model_dump_json(),
    )
    return OrderOut.model_validate(order)


@router.get("")
async def list_orders(
    customer_id: UUID | None = None,
    customer_email: str | None = None,
    status: OrderStatus | None = None,
    payment_status: PaymentStatus | None = None,
    older_than_hours: int | None = Query(default=None, ge=1),
    offset: int = 0,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: str | None = None,
    paginated: bool = False,
    session: AsyncSession = Depends(get_session),
) -> list[OrderOut] | OrderListOut:
    if customer_email:
        resolved_id = await fetch_customer_id_by_email(customer_email)
        if customer_id and customer_id != resolved_id:
            raise HTTPException(
                status_code=400,
                detail="customer_email does not match customer_id",
            )
        customer_id = resolved_id

    use_cursor = paginated or cursor is not None
    query = select(Order).options(selectinload(Order.line_items)).order_by(
        Order.created_at.desc(),
        Order.id.desc(),
    )
    if customer_id:
        query = query.where(Order.customer_id == customer_id)
    if status:
        query = query.where(Order.status == status)
    if payment_status:
        query = query.where(Order.payment_status == payment_status)
    if older_than_hours is not None:
        cutoff = datetime.now(UTC) - timedelta(hours=older_than_hours)
        query = query.where(Order.created_at <= cutoff)

    if use_cursor:
        if cursor:
            cursor_created_at, cursor_order_id = decode_order_cursor(cursor)
            query = query.where(
                or_(
                    Order.created_at < cursor_created_at,
                    and_(
                        Order.created_at == cursor_created_at,
                        Order.id < cursor_order_id,
                    ),
                )
            )
        result = await session.execute(query.limit(limit + 1))
        orders = list(result.scalars().all())
        next_cursor = None
        if len(orders) > limit:
            orders = orders[:limit]
            last = orders[-1]
            next_cursor = encode_order_cursor(last.created_at, last.id)
        return OrderListOut(
            orders=[OrderOut.model_validate(o) for o in orders],
            next_cursor=next_cursor,
            limit=limit,
        )

    result = await session.execute(query.offset(offset).limit(limit))
    return [OrderOut.model_validate(o) for o in result.scalars().all()]


@router.get("/stats")
async def order_stats(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return total order count, per-status breakdown, and revenue using SQL aggregation."""
    rows = await session.execute(
        select(
            Order.status,
            func.count().label("n"),
            func.coalesce(func.sum(Order.grand_total), 0).label("rev"),
        ).group_by(Order.status)
    )
    counts: dict[str, int] = {}
    total_revenue = Decimal("0")
    for row in rows:
        counts[row.status.value] = row.n
        total_revenue += Decimal(str(row.rev))
    total = sum(counts.values())
    avg_order_value = (
        (total_revenue / total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if total else Decimal("0")
    )
    return {
        "total": total,
        "by_status": counts,
        "total_revenue": str(total_revenue),
        "avg_order_value": str(avg_order_value),
    }


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> OrderOut:
    order = await get_order_or_404(session, order_id)
    return OrderOut.model_validate(order)


@router.get("/{order_id}/status", response_model=OrderStatusOut)
async def get_order_status(
    order_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> OrderStatusOut:
    cache_key = f"order:status:{order_id}"
    cached = await cache_get(cache_key)
    if cached:
        return OrderStatusOut.model_validate_json(cached)
    order = await get_order_or_404(session, order_id)
    status_out = OrderStatusOut(
        order_id=order.id,
        status=order.status,
        payment_status=order.payment_status,
        updated_at=order.updated_at,
    )
    await cache_set(cache_key, status_out.model_dump_json())
    return status_out


@router.patch("/{order_id}/status", response_model=OrderOut)
async def update_order_status(
    order_id: UUID,
    payload: OrderStatusUpdate,
    session: AsyncSession = Depends(get_session),
) -> OrderOut:
    order = await get_order_or_404(session, order_id)
    order = await transition_order(
        session,
        order,
        payload.status,
        f"order.status.{payload.status.value}",
    )
    return OrderOut.model_validate(order)


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel_order(
    order_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> OrderOut:
    order = await get_order_or_404(session, order_id)
    if order.status in {OrderStatus.CLOSED, OrderStatus.CANCELLED}:
        raise HTTPException(status_code=400, detail="Order cannot be cancelled")
    order = await transition_order(
        session,
        order,
        OrderStatus.CANCELLED,
        "order.cancelled",
        {"reason": "customer_request"},
    )
    return OrderOut.model_validate(order)


@router.post("/{order_id}/returns", response_model=OrderEventOut, status_code=201)
async def initiate_return(
    order_id: UUID,
    payload: ReturnRequest,
    session: AsyncSession = Depends(get_session),
) -> OrderEventOut:
    order = await get_order_or_404(session, order_id)
    if order.status not in {OrderStatus.DELIVERED, OrderStatus.SHIPPED, OrderStatus.CLOSED}:
        raise HTTPException(status_code=400, detail="Order is not eligible for return")
    event = await record_event(
        session,
        order,
        "order.return_initiated",
        order.status,
        order.status,
        {"reason": payload.reason, "line_items": [i.model_dump() for i in (payload.line_items or [])]},
    )
    await session.commit()
    await session.refresh(event)
    await publish_event(
        "orders.return_initiated",
        {"order_id": str(order.id), "reason": payload.reason},
    )
    return OrderEventOut.model_validate(event)


@router.get("/{order_id}/events", response_model=list[OrderEventOut])
async def list_order_events(
    order_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[OrderEventOut]:
    order = await get_order_or_404(session, order_id)
    return [OrderEventOut.model_validate(e) for e in sorted(order.events, key=lambda e: e.created_at)]
