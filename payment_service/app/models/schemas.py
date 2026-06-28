from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.postgres import TransactionStatus


class PaymentAuthorize(BaseModel):
    order_id: UUID
    customer_id: UUID
    amount: Decimal = Field(gt=0, decimal_places=2)
    currency: str = Field(default="USD", max_length=3)
    payment_method_token: str = Field(min_length=1, max_length=100)
    metadata: dict = Field(default_factory=dict)


class PaymentCapture(BaseModel):
    transaction_id: UUID
    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)


class PaymentRefund(BaseModel):
    transaction_id: UUID
    amount: Decimal | None = Field(default=None, gt=0, decimal_places=2)
    reason: str | None = Field(default=None, max_length=500)


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    order_id: UUID
    customer_id: UUID
    amount: Decimal
    currency: str
    status: TransactionStatus
    payment_method_token: str
    processor_ref: str | None
    authorized_amount: Decimal
    captured_amount: Decimal
    refunded_amount: Decimal
    correlation_id: str | None
    metadata: dict = Field(
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime
