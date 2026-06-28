from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_session
from app.models.postgres import CouponCode, Promotion
from app.models.schemas import (
    CouponCreate,
    CouponOut,
    CouponValidateOut,
    CouponValidateRequest,
    PromotionCreate,
    PromotionOut,
    PromotionUpdate,
)
from app.services.product_service import cache_delete_pattern, validate_coupon

router = APIRouter(tags=["promotions"])


@router.post("/promotions", response_model=PromotionOut, status_code=201)
async def create_promotion(
    payload: PromotionCreate,
    session: AsyncSession = Depends(get_session),
) -> PromotionOut:
    promotion = Promotion(**payload.model_dump())
    session.add(promotion)
    await session.commit()
    await session.refresh(promotion)
    await cache_delete_pattern("products:")
    return PromotionOut.model_validate(promotion)


@router.get("/promotions", response_model=list[PromotionOut])
async def list_promotions(
    active_only: bool = True,
    session: AsyncSession = Depends(get_session),
) -> list[PromotionOut]:
    query = select(Promotion)
    if active_only:
        query = query.where(Promotion.is_active.is_(True))
    result = await session.execute(query.order_by(Promotion.created_at.desc()))
    return [PromotionOut.model_validate(p) for p in result.scalars().all()]


@router.patch("/promotions/{promotion_id}", response_model=PromotionOut)
async def update_promotion(
    promotion_id: str,
    payload: PromotionUpdate,
    session: AsyncSession = Depends(get_session),
) -> PromotionOut:
    from uuid import UUID

    result = await session.execute(select(Promotion).where(Promotion.id == UUID(promotion_id)))
    promotion = result.scalar_one_or_none()
    if promotion is None:
        raise HTTPException(status_code=404, detail="Promotion not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(promotion, field, value)
    await session.commit()
    await session.refresh(promotion)
    await cache_delete_pattern("products:")
    return PromotionOut.model_validate(promotion)


@router.post("/coupons", response_model=CouponOut, status_code=201)
async def create_coupon(
    payload: CouponCreate,
    session: AsyncSession = Depends(get_session),
) -> CouponOut:
    code = payload.code.upper()
    result = await session.execute(select(Promotion).where(Promotion.id == payload.promotion_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Promotion not found")
    existing = await session.execute(select(CouponCode).where(CouponCode.code == code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Coupon code already exists")
    coupon = CouponCode(code=code, promotion_id=payload.promotion_id, max_uses=payload.max_uses)
    session.add(coupon)
    await session.commit()
    await session.refresh(coupon)
    return CouponOut.model_validate(coupon)


@router.post("/coupons/validate", response_model=CouponValidateOut)
async def validate_coupon_code(
    payload: CouponValidateRequest,
    session: AsyncSession = Depends(get_session),
) -> CouponValidateOut:
    valid, discount, message = await validate_coupon(session, payload.code, payload.subtotal)
    return CouponValidateOut(
        valid=valid,
        code=payload.code.upper(),
        discount_amount=discount,
        message=message,
    )
