from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.postgres import MovementType, ReservationStatus


class FulfillmentCenterCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    line1: str = Field(max_length=200)
    city: str = Field(max_length=100)
    state: str = Field(max_length=50)
    postal_code: str = Field(max_length=20)
    country: str = Field(default="US", max_length=2)


class FulfillmentCenterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    line1: str
    city: str
    state: str
    postal_code: str
    country: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StockLevelOut(BaseModel):
    fulfillment_center_id: UUID
    fulfillment_center_code: str | None = None
    sku: str
    on_hand: int
    reserved: int
    available: int
    reorder_point: int
    redis_available: int | None = None


class InventorySkuOut(BaseModel):
    sku: str
    total_on_hand: int
    total_reserved: int
    total_available: int
    locations: list[StockLevelOut]


class InventoryAdjust(BaseModel):
    sku: str = Field(max_length=50)
    fulfillment_center_id: UUID
    quantity_delta: int = Field(description="Positive to add stock, negative to remove")
    movement_type: MovementType = MovementType.ADJUST
    reference_type: str | None = Field(default=None, max_length=50)
    reference_id: UUID | None = None
    notes: str | None = None


class InventoryReserve(BaseModel):
    order_id: UUID
    sku: str = Field(max_length=50)
    fulfillment_center_id: UUID
    quantity: int = Field(gt=0)


class InventoryRelease(BaseModel):
    reservation_id: UUID | None = None
    order_id: UUID | None = None
    sku: str | None = Field(default=None, max_length=50)


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    sku: str
    fulfillment_center_id: UUID
    quantity: int
    status: ReservationStatus
    created_at: datetime
    released_at: datetime | None


class StockMovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sku: str
    fulfillment_center_id: UUID
    movement_type: MovementType
    quantity_delta: int
    reference_type: str | None
    reference_id: UUID | None
    notes: str | None
    created_at: datetime


class ReorderPointUpdate(BaseModel):
    sku: str = Field(max_length=50)
    fulfillment_center_id: UUID
    reorder_point: int = Field(ge=0)


class LowStockItemOut(BaseModel):
    sku: str
    product_name: str
    fulfillment_center_code: str
    available: int
    reorder_point: int
    recommended_order_qty: int
    preferred_supplier_id: UUID | None = None
