import secrets
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.postgres import Transaction, TransactionStatus


async def get_transaction_or_404(session: AsyncSession, transaction_id: UUID) -> Transaction:
    result = await session.execute(select(Transaction).where(Transaction.id == transaction_id))
    transaction = result.scalar_one_or_none()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


def _processor_ref() -> str:
    return f"proc_{secrets.token_hex(8)}"


async def authorize_payment(
    session: AsyncSession,
    order_id: UUID,
    customer_id: UUID,
    amount: Decimal,
    currency: str,
    payment_method_token: str,
    metadata: dict,
    correlation_id: str | None,
) -> Transaction:
    transaction = Transaction(
        order_id=order_id,
        customer_id=customer_id,
        amount=amount,
        currency=currency,
        status=TransactionStatus.AUTHORIZED,
        payment_method_token=payment_method_token,
        processor_ref=_processor_ref(),
        authorized_amount=amount,
        correlation_id=correlation_id,
        metadata_=metadata,
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction


async def capture_payment(
    session: AsyncSession,
    transaction: Transaction,
    amount: Decimal | None,
) -> Transaction:
    if transaction.status not in {
        TransactionStatus.AUTHORIZED,
        TransactionStatus.PARTIALLY_REFUNDED,
    }:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot capture transaction in status '{transaction.status.value}'",
        )

    capture_amount = amount if amount is not None else transaction.authorized_amount
    remaining = transaction.authorized_amount - transaction.captured_amount
    if capture_amount > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Capture amount {capture_amount} exceeds remaining authorized {remaining}",
        )

    transaction.captured_amount += capture_amount
    transaction.status = TransactionStatus.CAPTURED
    await session.commit()
    await session.refresh(transaction)
    return transaction


async def refund_payment(
    session: AsyncSession,
    transaction: Transaction,
    amount: Decimal | None,
    reason: str | None,
) -> Transaction:
    if transaction.status not in {TransactionStatus.CAPTURED, TransactionStatus.PARTIALLY_REFUNDED}:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot refund transaction in status '{transaction.status.value}'",
        )

    refund_amount = amount if amount is not None else (
        transaction.captured_amount - transaction.refunded_amount
    )
    refundable = transaction.captured_amount - transaction.refunded_amount
    if refund_amount > refundable:
        raise HTTPException(
            status_code=400,
            detail=f"Refund amount {refund_amount} exceeds refundable balance {refundable}",
        )

    transaction.refunded_amount += refund_amount
    if transaction.refunded_amount >= transaction.captured_amount:
        transaction.status = TransactionStatus.REFUNDED
    else:
        transaction.status = TransactionStatus.PARTIALLY_REFUNDED

    if reason:
        meta = dict(transaction.metadata_ or {})
        meta["last_refund_reason"] = reason
        transaction.metadata_ = meta

    await session.commit()
    await session.refresh(transaction)
    return transaction
