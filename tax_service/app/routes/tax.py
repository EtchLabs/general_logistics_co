from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_session
from app.models.postgres import LedgerStatus
from app.models.schemas import (
    LedgerEntryOut,
    TaxCalculateRequest,
    TaxCalculateResponse,
    TaxLineResult,
    TaxRateOut,
    TaxRemitRequest,
    TaxRemitResponse,
)
from app.services.tax_service import (
    calculate_and_record_tax,
    list_ledger_entries,
    list_tax_rates,
    remit_tax,
)

router = APIRouter(prefix="/tax", tags=["tax"])


@router.get("/rates", response_model=list[TaxRateOut])
async def get_rates(
    jurisdiction: str | None = Query(default=None),
    product_category: str | None = Query(default=None),
    active_only: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
) -> list[TaxRateOut]:
    rates = await list_tax_rates(session, jurisdiction, product_category, active_only)
    return [TaxRateOut.model_validate(r) for r in rates]


@router.post("/calculate", response_model=TaxCalculateResponse, status_code=201)
async def calculate_tax(
    payload: TaxCalculateRequest,
    session: AsyncSession = Depends(get_session),
) -> TaxCalculateResponse:
    line_items = [item.model_dump() for item in payload.line_items]
    line_results_raw, ledger_entries = await calculate_and_record_tax(
        session,
        order_id=payload.order_id,
        jurisdiction=payload.jurisdiction,
        line_items=line_items,
    )
    line_results = [TaxLineResult(**r) for r in line_results_raw]
    total_taxable = sum(r.taxable_amount for r in line_results)
    total_tax = sum(r.tax_amount for r in line_results)
    return TaxCalculateResponse(
        order_id=payload.order_id,
        jurisdiction=payload.jurisdiction,
        total_taxable=total_taxable,
        total_tax=total_tax,
        line_results=line_results,
        ledger_entries=[LedgerEntryOut.model_validate(e) for e in ledger_entries],
    )


@router.get("/ledger", response_model=list[LedgerEntryOut])
async def get_ledger(
    jurisdiction: str | None = Query(default=None),
    status: LedgerStatus | None = Query(default=None),
    order_id: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[LedgerEntryOut]:
    from uuid import UUID

    parsed_order_id = UUID(order_id) if order_id else None
    entries = await list_ledger_entries(session, jurisdiction, status, parsed_order_id)
    return [LedgerEntryOut.model_validate(e) for e in entries]


@router.post("/remit", response_model=TaxRemitResponse)
async def remit(
    payload: TaxRemitRequest,
    session: AsyncSession = Depends(get_session),
) -> TaxRemitResponse:
    remittance_id, total, count = await remit_tax(
        session,
        jurisdiction=payload.jurisdiction,
        period_start=payload.filing_period_start,
        period_end=payload.filing_period_end,
        reference=payload.reference,
    )
    return TaxRemitResponse(
        remittance_id=remittance_id,
        jurisdiction=payload.jurisdiction,
        filing_period_start=payload.filing_period_start,
        filing_period_end=payload.filing_period_end,
        total_remitted=total,
        entries_updated=count,
    )
