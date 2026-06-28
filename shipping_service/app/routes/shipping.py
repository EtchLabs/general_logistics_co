from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_session
from app.models.schemas import (
    LabelRequest,
    RateRequest,
    RateResponse,
    ShipmentOut,
    TrackingEventOut,
    TrackingOut,
)
from app.services.shipping_service import calculate_rates, create_label, get_tracking

router = APIRouter(prefix="/shipping", tags=["shipping"])


@router.post("/rates", response_model=RateResponse)
async def get_shipping_rates(payload: RateRequest) -> RateResponse:
    return calculate_rates(payload)


@router.post("/labels", response_model=ShipmentOut, status_code=201)
async def create_shipping_label(
    payload: LabelRequest,
    session: AsyncSession = Depends(get_session),
) -> ShipmentOut:
    shipment = await create_label(session, payload)
    return ShipmentOut.model_validate(shipment)


@router.get("/track/{tracking_number}", response_model=TrackingOut)
async def track_shipment(
    tracking_number: str,
    session: AsyncSession = Depends(get_session),
) -> TrackingOut:
    shipment, events = await get_tracking(session, tracking_number)
    return TrackingOut(
        tracking_number=shipment.tracking_number,
        carrier=shipment.carrier,
        service_level=shipment.service_level,
        status=shipment.status,
        shipment=ShipmentOut.model_validate(shipment),
        events=[TrackingEventOut.model_validate(event) for event in events],
    )
