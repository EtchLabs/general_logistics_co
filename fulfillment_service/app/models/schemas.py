from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.postgres import FulfillmentJobStatus


class PickListLineItem(BaseModel):
    sku: str
    product_name: str | None = None
    quantity: int = Field(gt=0)
    bin_location: str | None = None


class FulfillmentJobCreate(BaseModel):
    order_id: UUID
    fulfillment_center_id: UUID
    line_items: list[PickListLineItem] = Field(min_length=1)


class PickListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fulfillment_job_id: UUID
    line_items: list
    picker_id: str | None
    picked_quantity: int
    created_at: datetime


class FulfillmentJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    fulfillment_center_id: UUID
    status: FulfillmentJobStatus
    created_at: datetime
    updated_at: datetime
    pick_lists: list[PickListOut] = []


class FulfillmentJobStatusUpdate(BaseModel):
    status: FulfillmentJobStatus
