import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.postgres import Shipment, ShipmentStatus, TrackingEvent
from app.models.schemas import LabelRequest, RateQuote, RateRequest, RateResponse


MOCK_CARRIERS: list[tuple[str, str, Decimal, int]] = [
    ("GLC Ground", "ground", Decimal("8.99"), 5),
    ("GLC Express", "express", Decimal("14.99"), 2),
    ("GLC Overnight", "overnight", Decimal("24.99"), 1),
]


def calculate_rates(payload: RateRequest) -> RateResponse:
    weight_factor = max(Decimal("1"), payload.weight_oz / Decimal("16"))
    quotes = [
        RateQuote(
            carrier=carrier,
            service_level=service_level,
            cost=(base_cost * weight_factor).quantize(Decimal("0.01")),
            estimated_days=days,
        )
        for carrier, service_level, base_cost, days in MOCK_CARRIERS
    ]
    return RateResponse(quotes=quotes)


def generate_tracking_number(carrier: str) -> str:
    prefix = "".join(part[0] for part in carrier.split()[:2]).upper()
    return f"{prefix}{secrets.token_hex(6).upper()}"


def resolve_shipping_cost(payload: LabelRequest) -> Decimal:
    if payload.shipping_cost is not None:
        return payload.shipping_cost
    rates = calculate_rates(
        RateRequest(ship_to=payload.ship_to, weight_oz=payload.weight_oz)
    )
    for quote in rates.quotes:
        if quote.carrier == payload.carrier and quote.service_level == payload.service_level:
            return quote.cost
    raise HTTPException(status_code=400, detail="Unknown carrier or service level")


async def create_label(session: AsyncSession, payload: LabelRequest) -> Shipment:
    tracking_number = generate_tracking_number(payload.carrier)
    shipping_cost = resolve_shipping_cost(payload)
    shipment = Shipment(
        order_id=payload.order_id,
        fulfillment_job_id=payload.fulfillment_job_id,
        carrier=payload.carrier,
        service_level=payload.service_level,
        tracking_number=tracking_number,
        label_url=f"https://labels.glc.local/{tracking_number}.pdf",
        weight_oz=payload.weight_oz,
        shipping_cost=shipping_cost,
        status=ShipmentStatus.LABEL_CREATED,
        ship_to_address=payload.ship_to.model_dump(),
    )
    session.add(shipment)
    await session.flush()

    label_event = TrackingEvent(
        shipment_id=shipment.id,
        event_type="label_created",
        location="GLC Shipping Hub",
        description=f"Shipping label created via {payload.carrier} {payload.service_level}",
        occurred_at=datetime.now(UTC),
    )
    session.add(label_event)
    await session.commit()
    await session.refresh(shipment)
    return shipment


async def get_tracking(session: AsyncSession, tracking_number: str) -> tuple[Shipment, list[TrackingEvent]]:
    result = await session.execute(
        select(Shipment)
        .options(selectinload(Shipment.tracking_events))
        .where(Shipment.tracking_number == tracking_number)
    )
    shipment = result.scalar_one_or_none()
    if shipment is None:
        raise HTTPException(status_code=404, detail="Tracking number not found")

    events = sorted(shipment.tracking_events, key=lambda event: event.occurred_at)
    if len(events) == 1 and shipment.status == ShipmentStatus.LABEL_CREATED:
        in_transit = TrackingEvent(
            shipment_id=shipment.id,
            event_type="in_transit",
            location="Regional Sort Facility",
            description="Package departed origin facility",
            occurred_at=datetime.now(UTC) - timedelta(hours=6),
        )
        events = [events[0], in_transit]
        shipment.status = ShipmentStatus.IN_TRANSIT

    return shipment, events
