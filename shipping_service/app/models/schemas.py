from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.postgres import ShipmentStatus


class Address(BaseModel):
    line1: str
    line2: str | None = None
    city: str
    state: str
    postal_code: str
    country: str = "US"


class RateRequest(BaseModel):
    ship_to: Address
    weight_oz: Decimal = Field(gt=0)
    origin_postal_code: str = Field(default="10001", max_length=20)


class RateQuote(BaseModel):
    carrier: str
    service_level: str
    cost: Decimal
    estimated_days: int


class RateResponse(BaseModel):
    quotes: list[RateQuote]


class LabelRequest(BaseModel):
    order_id: UUID
    fulfillment_job_id: UUID | None = None
    carrier: str = Field(max_length=50)
    service_level: str = Field(max_length=50)
    ship_to: Address
    weight_oz: Decimal = Field(gt=0)
    shipping_cost: Decimal | None = None


class TrackingEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shipment_id: UUID
    event_type: str
    location: str | None
    description: str
    occurred_at: datetime


class ShipmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    fulfillment_job_id: UUID | None
    carrier: str
    service_level: str
    tracking_number: str
    label_url: str
    weight_oz: Decimal
    shipping_cost: Decimal
    status: ShipmentStatus
    ship_to_address: dict
    created_at: datetime


class TrackingOut(BaseModel):
    tracking_number: str
    carrier: str
    service_level: str
    status: ShipmentStatus
    shipment: ShipmentOut
    events: list[TrackingEventOut]
