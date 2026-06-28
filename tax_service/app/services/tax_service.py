import uuid
from datetime import UTC, date, datetime, time
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.postgres import LedgerStatus, TaxCollectedLedger, TaxRate


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def find_active_rate(
    session: AsyncSession,
    jurisdiction: str,
    product_category: str,
    as_of: date | None = None,
) -> TaxRate | None:
    effective = as_of or date.today()
    result = await session.execute(
        select(TaxRate).where(
            TaxRate.jurisdiction == jurisdiction,
            TaxRate.product_category == product_category,
            TaxRate.is_active.is_(True),
            TaxRate.effective_from <= effective,
            (TaxRate.effective_to.is_(None)) | (TaxRate.effective_to >= effective),
        )
    )
    rate = result.scalar_one_or_none()
    if rate is None and product_category != "general":
        return await find_active_rate(session, jurisdiction, "general", effective)
    return rate


async def list_tax_rates(
    session: AsyncSession,
    jurisdiction: str | None = None,
    product_category: str | None = None,
    active_only: bool = True,
) -> list[TaxRate]:
    query = select(TaxRate)
    if jurisdiction:
        query = query.where(TaxRate.jurisdiction == jurisdiction)
    if product_category:
        query = query.where(TaxRate.product_category == product_category)
    if active_only:
        query = query.where(TaxRate.is_active.is_(True))
    query = query.order_by(TaxRate.jurisdiction, TaxRate.product_category)
    result = await session.execute(query)
    return list(result.scalars().all())


async def calculate_and_record_tax(
    session: AsyncSession,
    order_id: uuid.UUID,
    jurisdiction: str,
    line_items: list[dict],
) -> tuple[list[dict], list[TaxCollectedLedger]]:
    line_results: list[dict] = []
    ledger_entries: list[TaxCollectedLedger] = []

    for item in line_items:
        rate = await find_active_rate(session, jurisdiction, item["product_category"])
        if rate is None:
            raise HTTPException(
                status_code=404,
                detail=f"No tax rate found for jurisdiction '{jurisdiction}' "
                f"and category '{item['product_category']}'",
            )

        taxable = Decimal(str(item["taxable_amount"]))
        tax_amount = _quantize(taxable * rate.rate_percent / Decimal("100"))

        ledger = TaxCollectedLedger(
            order_id=order_id,
            jurisdiction=jurisdiction,
            tax_rate_id=rate.id,
            taxable_amount=taxable,
            tax_amount=tax_amount,
            status=LedgerStatus.COLLECTED,
        )
        session.add(ledger)
        ledger_entries.append(ledger)

        line_results.append(
            {
                "sku": item["sku"],
                "product_category": item["product_category"],
                "taxable_amount": taxable,
                "rate_percent": rate.rate_percent,
                "tax_amount": tax_amount,
                "tax_rate_id": rate.id,
            }
        )

    await session.commit()
    for entry in ledger_entries:
        await session.refresh(entry)
    return line_results, ledger_entries


async def list_ledger_entries(
    session: AsyncSession,
    jurisdiction: str | None = None,
    status: LedgerStatus | None = None,
    order_id: uuid.UUID | None = None,
) -> list[TaxCollectedLedger]:
    query = select(TaxCollectedLedger)
    if jurisdiction:
        query = query.where(TaxCollectedLedger.jurisdiction == jurisdiction)
    if status:
        query = query.where(TaxCollectedLedger.status == status)
    if order_id:
        query = query.where(TaxCollectedLedger.order_id == order_id)
    query = query.order_by(TaxCollectedLedger.created_at.desc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def remit_tax(
    session: AsyncSession,
    jurisdiction: str,
    period_start: date,
    period_end: date,
    reference: str | None,
) -> tuple[uuid.UUID, Decimal, int]:
    period_start_dt = datetime.combine(period_start, time.min, tzinfo=UTC)
    period_end_dt = datetime.combine(period_end, time.max, tzinfo=UTC)
    result = await session.execute(
        select(TaxCollectedLedger).where(
            TaxCollectedLedger.jurisdiction == jurisdiction,
            TaxCollectedLedger.status == LedgerStatus.COLLECTED,
            TaxCollectedLedger.created_at >= period_start_dt,
            TaxCollectedLedger.created_at <= period_end_dt,
        )
    )
    entries = list(result.scalars().all())
    if not entries:
        raise HTTPException(
            status_code=404,
            detail="No collected tax entries found for the specified jurisdiction and period",
        )

    remittance_id = uuid.uuid4()
    total = sum(entry.tax_amount for entry in entries)

    await session.execute(
        update(TaxCollectedLedger)
        .where(TaxCollectedLedger.id.in_([e.id for e in entries]))
        .values(status=LedgerStatus.REMITTED, remittance_id=remittance_id)
    )
    await session.commit()

    if reference:
        pass  # reference stored in response only for mock processor integration

    return remittance_id, total, len(entries)
