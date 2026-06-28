from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.postgres import LoyaltyTier, TicketPriority, TicketStatus


class CustomerRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)


class CustomerLogin(BaseModel):
    email: EmailStr
    password: str


class CustomerUpdate(BaseModel):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    loyalty_tier: LoyaltyTier | None = None
    is_wholesale: bool | None = None


class CustomerTagsUpdate(BaseModel):
    loyalty_tier: LoyaltyTier | None = None
    is_wholesale: bool | None = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    first_name: str
    last_name: str
    phone: str | None
    loyalty_tier: LoyaltyTier
    is_wholesale: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CustomerTagsOut(BaseModel):
    customer_id: UUID
    loyalty_tier: LoyaltyTier
    is_wholesale: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    customer: CustomerOut


class PasswordResetRequest(BaseModel):
    email: EmailStr


class AddressCreate(BaseModel):
    label: str = Field(default="Home", max_length=50)
    line1: str = Field(max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(max_length=100)
    state: str = Field(max_length=50)
    postal_code: str = Field(max_length=20)
    country: str = Field(default="US", max_length=2)
    is_default: bool = False


class AddressUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=50)
    line1: str | None = Field(default=None, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default=None, max_length=2)
    is_default: bool | None = None


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    label: str
    line1: str
    line2: str | None
    city: str
    state: str
    postal_code: str
    country: str
    is_default: bool
    created_at: datetime


class PaymentMethodCreate(BaseModel):
    label: str = Field(default="Card", max_length=50)
    card_number: str = Field(min_length=13, max_length=19)
    card_brand: str = Field(max_length=20)
    exp_month: int = Field(ge=1, le=12)
    exp_year: int = Field(ge=2024, le=2100)
    is_default: bool = False


class PaymentMethodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    label: str
    token: str
    last_four: str
    card_brand: str
    exp_month: int
    exp_year: int
    is_default: bool
    created_at: datetime


class SupportTicketCreate(BaseModel):
    subject: str = Field(max_length=200)
    description: str
    priority: TicketPriority = TicketPriority.NORMAL


class SupportTicketUpdate(BaseModel):
    status: TicketStatus | None = None
    priority: TicketPriority | None = None


class SupportTicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    subject: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class TicketMessageCreate(BaseModel):
    message: str = Field(min_length=1)


class TicketMessageOut(BaseModel):
    id: str
    ticket_id: UUID
    customer_id: UUID
    message: str
    author_type: str
    created_at: datetime


class ActivityLogOut(BaseModel):
    id: str
    customer_id: UUID
    action: str
    metadata: dict
    created_at: datetime


class PreferencesOut(BaseModel):
    customer_id: UUID
    preferences: dict


class PreferencesUpdate(BaseModel):
    preferences: dict


class PurchaseHistoryItem(BaseModel):
    order_id: UUID | None = None
    placed_at: datetime | None = None
    total: float | None = None
    status: str | None = None


class AccountStatementLine(BaseModel):
    date: datetime | None = None
    description: str
    amount: float
    balance: float | None = None
