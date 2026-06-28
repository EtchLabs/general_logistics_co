from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.postgres import OrderStatus, OrderType, PaymentStatus


class AddressInput(BaseModel):
    label: str = "Shipping"
    line1: str
    line2: str | None = None
    city: str
    state: str
    postal_code: str
    country: str = "US"


class OrderLineInput(BaseModel):
    sku: str = Field(min_length=1, max_length=50)
    quantity: int = Field(ge=1)


class OrderCreate(BaseModel):
    customer_id: UUID
    order_type: OrderType = OrderType.B2C
    line_items: list[OrderLineInput] = Field(min_length=1)
    shipping_address: AddressInput
    coupon_code: str | None = None
    shipping_total: Decimal = Field(default=Decimal("0"), ge=0)


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class ReturnRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    line_items: list[OrderLineInput] | None = None


class OrderLineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    sku: str
    product_name: str
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class OrderEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    event_type: str
    from_status: str | None
    to_status: str | None
    details: dict
    created_at: datetime


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    order_type: OrderType
    status: OrderStatus
    payment_status: PaymentStatus
    subtotal: Decimal
    tax_total: Decimal
    shipping_total: Decimal
    discount_total: Decimal
    grand_total: Decimal
    coupon_code: str | None
    shipping_address: dict
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    line_items: list[OrderLineItemOut] = Field(default_factory=list)


class OrderStatusOut(BaseModel):
    order_id: UUID
    status: OrderStatus
    payment_status: PaymentStatus
    updated_at: datetime


class OrderListOut(BaseModel):
    orders: list[OrderOut]
    next_cursor: str | None = None
    limit: int
