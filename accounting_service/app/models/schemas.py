from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.postgres import AccountType


class AccountCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    account_type: AccountType


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    account_type: AccountType
    balance: Decimal
    is_active: bool
    created_at: datetime


class LedgerLineCreate(BaseModel):
    account_id: UUID
    debit: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    description: str | None = Field(default=None, max_length=500)


class JournalEntryCreate(BaseModel):
    entry_date: date
    description: str = Field(min_length=1, max_length=500)
    reference: str | None = Field(default=None, max_length=100)
    lines: list[LedgerLineCreate] = Field(min_length=2)


class LedgerLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    debit: Decimal
    credit: Decimal
    description: str | None


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    entry_date: date
    description: str
    reference: str | None
    created_at: datetime
    lines: list[LedgerLineOut]


class IncomeStatementOut(BaseModel):
    revenue_total: Decimal
    expense_total: Decimal
    net_income: Decimal
    revenue_accounts: list[AccountOut]
    expense_accounts: list[AccountOut]
