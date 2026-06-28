from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.postgres import get_session
from app.models.postgres import FulfillmentCenter, SkuStock
from app.models.schemas import (
    InventoryAdjust,
    InventoryRelease,
    InventoryReserve,
    InventorySkuOut,
    LowStockItemOut,
    ReorderPointUpdate,
    ReservationOut,
    StockMovementOut,
)
from app.services.inventory_service import (
    adjust_stock,
    get_inventory_for_sku,
    get_or_create_stock,
    release_reservation,
    reserve_stock,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


async def fetch_pricing_info(sku: str) -> dict:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{settings.product_service_url}/pricing/{sku}")
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        return response.json()


async def fetch_product_name(sku: str) -> str:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(f"{settings.product_service_url}/products/sku/{sku}")
        if response.status_code == 404:
            return sku
        response.raise_for_status()
        return response.json().get("name", sku)


@router.get("/below-reorder-point", response_model=list[LowStockItemOut])
async def list_below_reorder_point(
    session: AsyncSession = Depends(get_session),
) -> list[LowStockItemOut]:
    result = await session.execute(
        select(SkuStock, FulfillmentCenter)
        .join(FulfillmentCenter, SkuStock.fulfillment_center_id == FulfillmentCenter.id)
        .where(SkuStock.reorder_point > 0)
        .order_by(SkuStock.sku, FulfillmentCenter.code)
    )
    items: list[LowStockItemOut] = []
    product_names: dict[str, str] = {}
    pricing_cache: dict[str, dict] = {}

    for stock, fc in result.all():
        available = stock.on_hand - stock.reserved
        if available >= stock.reorder_point:
            continue
        if stock.sku not in product_names:
            product_names[stock.sku] = await fetch_product_name(stock.sku)
        if stock.sku not in pricing_cache:
            pricing_cache[stock.sku] = await fetch_pricing_info(stock.sku)
        pricing = pricing_cache[stock.sku]
        threshold = pricing.get("reorder_threshold") or stock.reorder_point
        recommended = max(threshold * 10, stock.reorder_point * 2)
        items.append(
            LowStockItemOut(
                sku=stock.sku,
                product_name=product_names[stock.sku],
                fulfillment_center_code=fc.code,
                available=available,
                reorder_point=stock.reorder_point,
                recommended_order_qty=recommended,
                preferred_supplier_id=pricing.get("supplier_id"),
            )
        )
    return items


@router.patch("/reorder-point", response_model=dict)
async def set_reorder_point(
    payload: ReorderPointUpdate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    stock = await get_or_create_stock(session, payload.fulfillment_center_id, payload.sku)
    stock.reorder_point = payload.reorder_point
    await session.commit()
    return {
        "sku": payload.sku,
        "fulfillment_center_id": str(payload.fulfillment_center_id),
        "reorder_point": payload.reorder_point,
    }


@router.get("/{sku}", response_model=InventorySkuOut)
async def get_inventory_by_sku(
    sku: str,
    fulfillment_center_id: UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> InventorySkuOut:
    return await get_inventory_for_sku(session, sku, fulfillment_center_id)


@router.post("/adjust", response_model=StockMovementOut)
async def adjust_inventory(
    payload: InventoryAdjust,
    session: AsyncSession = Depends(get_session),
) -> StockMovementOut:
    _, movement = await adjust_stock(
        session,
        sku=payload.sku,
        fulfillment_center_id=payload.fulfillment_center_id,
        quantity_delta=payload.quantity_delta,
        movement_type=payload.movement_type,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        notes=payload.notes,
    )
    await session.commit()
    await session.refresh(movement)
    return StockMovementOut.model_validate(movement)


@router.post("/reserve", response_model=ReservationOut, status_code=201)
async def reserve_inventory(
    payload: InventoryReserve,
    session: AsyncSession = Depends(get_session),
) -> ReservationOut:
    reservation = await reserve_stock(
        session,
        order_id=payload.order_id,
        sku=payload.sku,
        fulfillment_center_id=payload.fulfillment_center_id,
        quantity=payload.quantity,
    )
    await session.commit()
    await session.refresh(reservation)
    return ReservationOut.model_validate(reservation)


@router.post("/release", response_model=list[ReservationOut])
async def release_inventory(
    payload: InventoryRelease,
    session: AsyncSession = Depends(get_session),
) -> list[ReservationOut]:
    reservations = await release_reservation(
        session,
        reservation_id=payload.reservation_id,
        order_id=payload.order_id,
        sku=payload.sku,
    )
    await session.commit()
    for reservation in reservations:
        await session.refresh(reservation)
    return [ReservationOut.model_validate(r) for r in reservations]
