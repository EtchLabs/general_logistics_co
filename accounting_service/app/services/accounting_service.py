from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.postgres import Account, AccountType, JournalEntry, LedgerLine
from app.models.schemas import JournalEntryCreate


async def get_account_or_404(session: AsyncSession, account_id: UUID) -> Account:
    result = await session.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


async def create_journal_entry(
    session: AsyncSession, payload: JournalEntryCreate
) -> JournalEntry:
    total_debit = sum((line.debit for line in payload.lines), Decimal("0"))
    total_credit = sum((line.credit for line in payload.lines), Decimal("0"))
    if total_debit != total_credit:
        raise HTTPException(
            status_code=400,
            detail=f"Journal entry must balance: debits={total_debit}, credits={total_credit}",
        )
    if total_debit == Decimal("0"):
        raise HTTPException(status_code=400, detail="Journal entry must have non-zero amounts")

    entry = JournalEntry(
        entry_date=payload.entry_date,
        description=payload.description,
        reference=payload.reference,
    )
    session.add(entry)
    await session.flush()

    for line_payload in payload.lines:
        account = await get_account_or_404(session, line_payload.account_id)
        if not account.is_active:
            raise HTTPException(status_code=400, detail=f"Account {account.code} is inactive")

        line = LedgerLine(
            journal_entry_id=entry.id,
            account_id=line_payload.account_id,
            debit=line_payload.debit,
            credit=line_payload.credit,
            description=line_payload.description,
        )
        session.add(line)
        account.balance += line_payload.debit - line_payload.credit

    await session.commit()
    result = await session.execute(
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .where(JournalEntry.id == entry.id)
    )
    return result.scalar_one()


async def get_income_statement(session: AsyncSession) -> dict:
    result = await session.execute(
        select(Account).where(
            Account.account_type.in_([AccountType.REVENUE, AccountType.EXPENSE]),
            Account.is_active.is_(True),
        )
    )
    accounts = result.scalars().all()

    revenue_accounts = [a for a in accounts if a.account_type == AccountType.REVENUE]
    expense_accounts = [a for a in accounts if a.account_type == AccountType.EXPENSE]

    revenue_total = sum((abs(a.balance) for a in revenue_accounts), Decimal("0"))
    expense_total = sum((abs(a.balance) for a in expense_accounts), Decimal("0"))

    return {
        "revenue_total": revenue_total,
        "expense_total": expense_total,
        "net_income": revenue_total - expense_total,
        "revenue_accounts": revenue_accounts,
        "expense_accounts": expense_accounts,
    }
