from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.postgres import LedgerStatus


class TaxRateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    jurisdiction: str
    state: str
    product_category: str
    rate_percent: Decimal
    effective_from: date
    effective_to: date | None
    is_active: bool
    created_at: datetime


class TaxLineItem(BaseModel):
    sku: str = Field(max_length=50)
    product_category: str = Field(default="general", max_length=50)
    taxable_amount: Decimal = Field(gt=0, decimal_places=2)


class TaxCalculateRequest(BaseModel):
    order_id: UUID
    jurisdiction: str = Field(max_length=100)
    state: str = Field(max_length=2)
    line_items: list[TaxLineItem] = Field(min_length=1)


class TaxLineResult(BaseModel):
    sku: str
    product_category: str
    taxable_amount: Decimal
    rate_percent: Decimal
    tax_amount: Decimal
    tax_rate_id: UUID


class TaxCalculateResponse(BaseModel):
    order_id: UUID
    jurisdiction: str
    total_taxable: Decimal
    total_tax: Decimal
    line_results: list[TaxLineResult]
    ledger_entries: list["LedgerEntryOut"]


class LedgerEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    jurisdiction: str
    tax_rate_id: UUID
    taxable_amount: Decimal
    tax_amount: Decimal
    status: LedgerStatus
    remittance_id: UUID | None
    created_at: datetime


class TaxRemitRequest(BaseModel):
    jurisdiction: str = Field(max_length=100)
    filing_period_start: date
    filing_period_end: date
    reference: str | None = Field(default=None, max_length=100)


class TaxRemitResponse(BaseModel):
    remittance_id: UUID
    jurisdiction: str
    filing_period_start: date
    filing_period_end: date
    total_remitted: Decimal
    entries_updated: int


TaxCalculateResponse.model_rebuild()
