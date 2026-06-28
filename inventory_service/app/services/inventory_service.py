from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.redis import get_redis
from app.models.postgres import (
    FulfillmentCenter,
    MovementType,
    Reservation,
    ReservationStatus,
    SkuStock,
    StockMovement,
)
from app.models.schemas import InventorySkuOut, StockLevelOut


def stock_counter_key(fulfillment_center_id: UUID, sku: str) -> str:
    settings = get_settings()
    return f"{settings.stock_counter_key_prefix}:{fulfillment_center_id}:{sku}"


async def sync_stock_counter(fulfillment_center_id: UUID, sku: str, available: int) -> None:
    await get_redis().set(stock_counter_key(fulfillment_center_id, sku), available)


async def get_redis_available(fulfillment_center_id: UUID, sku: str) -> int | None:
    value = await get_redis().get(stock_counter_key(fulfillment_center_id, sku))
    return int(value) if value is not None else None


async def get_fulfillment_center_or_404(
    session: AsyncSession, fulfillment_center_id: UUID
) -> FulfillmentCenter:
    result = await session.execute(
        select(FulfillmentCenter).where(FulfillmentCenter.id == fulfillment_center_id)
    )
    fc = result.scalar_one_or_none()
    if fc is None:
        raise HTTPException(status_code=404, detail="Fulfillment center not found")
    return fc


async def get_or_create_stock(
    session: AsyncSession, fulfillment_center_id: UUID, sku: str
) -> SkuStock:
    result = await session.execute(
        select(SkuStock).where(
            SkuStock.fulfillment_center_id == fulfillment_center_id,
            SkuStock.sku == sku,
        )
    )
    stock = result.scalar_one_or_none()
    if stock is None:
        stock = SkuStock(
            fulfillment_center_id=fulfillment_center_id,
            sku=sku,
            on_hand=0,
            reserved=0,
        )
        session.add(stock)
        await session.flush()
    return stock


async def record_movement(
    session: AsyncSession,
    *,
    sku: str,
    fulfillment_center_id: UUID,
    movement_type: MovementType,
    quantity_delta: int,
    reference_type: str | None = None,
    reference_id: UUID | None = None,
    notes: str | None = None,
) -> StockMovement:
    movement = StockMovement(
        sku=sku,
        fulfillment_center_id=fulfillment_center_id,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
    )
    session.add(movement)
    return movement


async def get_inventory_for_sku(
    session: AsyncSession, sku: str, fulfillment_center_id: UUID | None = None
) -> InventorySkuOut:
    query = (
        select(SkuStock, FulfillmentCenter)
        .join(FulfillmentCenter, SkuStock.fulfillment_center_id == FulfillmentCenter.id)
        .where(SkuStock.sku == sku)
    )
    if fulfillment_center_id is not None:
        query = query.where(SkuStock.fulfillment_center_id == fulfillment_center_id)

    result = await session.execute(query)
    rows = result.all()

    locations: list[StockLevelOut] = []
    total_on_hand = 0
    total_reserved = 0

    for stock, fc in rows:
        available = stock.on_hand - stock.reserved
        redis_available = await get_redis_available(stock.fulfillment_center_id, sku)
        locations.append(
            StockLevelOut(
                fulfillment_center_id=stock.fulfillment_center_id,
                fulfillment_center_code=fc.code,
                sku=stock.sku,
                on_hand=stock.on_hand,
                reserved=stock.reserved,
                available=available,
                reorder_point=stock.reorder_point,
                redis_available=redis_available,
            )
        )
        total_on_hand += stock.on_hand
        total_reserved += stock.reserved

    return InventorySkuOut(
        sku=sku,
        total_on_hand=total_on_hand,
        total_reserved=total_reserved,
        total_available=total_on_hand - total_reserved,
        locations=locations,
    )


async def adjust_stock(
    session: AsyncSession,
    *,
    sku: str,
    fulfillment_center_id: UUID,
    quantity_delta: int,
    movement_type: MovementType,
    reference_type: str | None = None,
    reference_id: UUID | None = None,
    notes: str | None = None,
) -> tuple[SkuStock, StockMovement]:
    await get_fulfillment_center_or_404(session, fulfillment_center_id)
    stock = await get_or_create_stock(session, fulfillment_center_id, sku)

    new_on_hand = stock.on_hand + quantity_delta
    if new_on_hand < stock.reserved:
        raise HTTPException(
            status_code=409,
            detail="Adjustment would leave on-hand below reserved quantity",
        )
    if new_on_hand < 0:
        raise HTTPException(status_code=409, detail="Insufficient on-hand stock")

    stock.on_hand = new_on_hand
    movement = await record_movement(
        session,
        sku=sku,
        fulfillment_center_id=fulfillment_center_id,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
    )
    await sync_stock_counter(fulfillment_center_id, sku, stock.on_hand - stock.reserved)
    return stock, movement


async def reserve_stock(
    session: AsyncSession,
    *,
    order_id: UUID,
    sku: str,
    fulfillment_center_id: UUID,
    quantity: int,
) -> Reservation:
    await get_fulfillment_center_or_404(session, fulfillment_center_id)
    stock = await get_or_create_stock(session, fulfillment_center_id, sku)

    available = stock.on_hand - stock.reserved
    if available < quantity:
        raise HTTPException(status_code=409, detail="Insufficient available stock")

    stock.reserved += quantity
    reservation = Reservation(
        order_id=order_id,
        sku=sku,
        fulfillment_center_id=fulfillment_center_id,
        quantity=quantity,
        status=ReservationStatus.ACTIVE,
    )
    session.add(reservation)
    await record_movement(
        session,
        sku=sku,
        fulfillment_center_id=fulfillment_center_id,
        movement_type=MovementType.RESERVE,
        quantity_delta=-quantity,
        reference_type="order",
        reference_id=order_id,
    )
    await sync_stock_counter(fulfillment_center_id, sku, stock.on_hand - stock.reserved)
    return reservation


async def release_reservation(
    session: AsyncSession,
    *,
    reservation_id: UUID | None = None,
    order_id: UUID | None = None,
    sku: str | None = None,
) -> list[Reservation]:
    if reservation_id is None and order_id is None:
        raise HTTPException(
            status_code=400, detail="Provide reservation_id or order_id (and optional sku)"
        )

    query = select(Reservation).where(Reservation.status == ReservationStatus.ACTIVE)
    if reservation_id is not None:
        query = query.where(Reservation.id == reservation_id)
    if order_id is not None:
        query = query.where(Reservation.order_id == order_id)
    if sku is not None:
        query = query.where(Reservation.sku == sku)

    result = await session.execute(query)
    reservations = list(result.scalars().all())
    if not reservations:
        raise HTTPException(status_code=404, detail="No active reservations found")

    released: list[Reservation] = []
    for reservation in reservations:
        stock = await get_or_create_stock(
            session, reservation.fulfillment_center_id, reservation.sku
        )
        stock.reserved = max(0, stock.reserved - reservation.quantity)
        reservation.status = ReservationStatus.RELEASED
        reservation.released_at = datetime.now(UTC)
        await record_movement(
            session,
            sku=reservation.sku,
            fulfillment_center_id=reservation.fulfillment_center_id,
            movement_type=MovementType.RELEASE,
            quantity_delta=reservation.quantity,
            reference_type="reservation",
            reference_id=reservation.id,
        )
        await sync_stock_counter(
            reservation.fulfillment_center_id,
            reservation.sku,
            stock.on_hand - stock.reserved,
        )
        released.append(reservation)

    return released
