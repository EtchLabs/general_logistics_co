from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_session
from app.models.postgres import FulfillmentCenter
from app.models.schemas import FulfillmentCenterCreate, FulfillmentCenterOut

router = APIRouter(prefix="/fulfillment-centers", tags=["fulfillment-centers"])


@router.get("", response_model=list[FulfillmentCenterOut])
async def list_fulfillment_centers(
    session: AsyncSession = Depends(get_session),
) -> list[FulfillmentCenterOut]:
    result = await session.execute(select(FulfillmentCenter).order_by(FulfillmentCenter.code))
    return [FulfillmentCenterOut.model_validate(fc) for fc in result.scalars().all()]


@router.post("", response_model=FulfillmentCenterOut, status_code=201)
async def create_fulfillment_center(
    payload: FulfillmentCenterCreate,
    session: AsyncSession = Depends(get_session),
) -> FulfillmentCenterOut:
    existing = await session.execute(
        select(FulfillmentCenter).where(FulfillmentCenter.code == payload.code.upper())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Fulfillment center code already exists")

    fc = FulfillmentCenter(code=payload.code.upper(), **payload.model_dump(exclude={"code"}))
    session.add(fc)
    await session.commit()
    await session.refresh(fc)
    return FulfillmentCenterOut.model_validate(fc)
