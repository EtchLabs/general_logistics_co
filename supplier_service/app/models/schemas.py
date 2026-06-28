from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.postgres import InvoiceStatus, POStatus, ReceiptStatus


class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    contact_email: EmailStr
    contact_phone: str | None = Field(default=None, max_length=30)
    payment_terms: str = Field(default="net_30", max_length=50)
    lead_time_days: int = Field(default=7, ge=0)
    reliability_score: Decimal = Field(default=Decimal("85.00"), ge=0, le=100)
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str = Field(default="US", max_length=2)


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=30)
    payment_terms: str | None = Field(default=None, max_length=50)
    lead_time_days: int | None = Field(default=None, ge=0)
    reliability_score: Decimal | None = Field(default=None, ge=0, le=100)
    is_active: bool | None = None
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=2)


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    contact_email: EmailStr
    contact_phone: str | None
    payment_terms: str
    lead_time_days: int
    reliability_score: Decimal
    is_active: bool
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str
    created_at: datetime
    updated_at: datetime


class POLineItemCreate(BaseModel):
    sku: str = Field(max_length=50)
    product_name: str = Field(max_length=200)
    quantity: int = Field(gt=0)
    unit_cost: Decimal = Field(gt=0, decimal_places=2)


class POLineItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_order_id: UUID
    sku: str
    product_name: str
    quantity: int
    unit_cost: Decimal
    line_total: Decimal


class PurchaseOrderCreate(BaseModel):
    supplier_id: UUID
    expected_delivery_date: date | None = None
    notes: str | None = None
    line_items: list[POLineItemCreate] = Field(min_length=1)
    submit: bool = False


class PurchaseOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    po_number: str
    supplier_id: UUID
    status: POStatus
    total_amount: Decimal
    expected_delivery_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    line_items: list[POLineItemOut] = []


class PurchaseOrderUpdate(BaseModel):
    status: POStatus | None = None
    expected_delivery_date: date | None = None
    notes: str | None = None


class POShipmentCreate(BaseModel):
    tracking_number: str = Field(max_length=100)
    shipped_at: datetime | None = None
    line_items: list[dict] = Field(default_factory=list)


class ReceiptLineItemOut(BaseModel):
    sku: str
    quantity_ordered: int
    quantity_received: int
    unit_cost: Decimal


class GoodsReceiptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    purchase_order_id: UUID
    receipt_number: str
    received_at: datetime
    status: ReceiptStatus
    line_items: list[ReceiptLineItemOut] = []


class SupplierInvoiceLineItemOut(BaseModel):
    sku: str
    quantity: int
    unit_cost: Decimal
    line_total: Decimal


class SupplierInvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_number: str
    supplier_id: UUID
    purchase_order_id: UUID
    status: InvoiceStatus
    total_amount: Decimal
    invoice_date: date
    due_date: date
    line_items: list[SupplierInvoiceLineItemOut] = []


class DiscrepancyOut(BaseModel):
    type: str
    sku: str
    po_quantity: int
    received_quantity: int
    invoiced_quantity: int
    notes: str


class SupplierInvoiceDetailOut(SupplierInvoiceOut):
    match_status: str
    discrepancies: list[DiscrepancyOut] = []
    match_notes: str | None = None


class InvoiceMatchAction(BaseModel):
    action: str = Field(pattern="^(approve|hold|dispute)$")
    notes: str | None = None
    discrepancy_resolutions: list[dict] = Field(default_factory=list)


class InvoiceMatchResultOut(BaseModel):
    id: UUID
    status: InvoiceStatus
    match_status: str
    match_notes: str | None = None
