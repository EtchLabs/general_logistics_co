from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_session
from app.models.schemas import (
    PaymentAuthorize,
    PaymentCapture,
    PaymentRefund,
    TransactionOut,
)
from app.services.payment_service import (
    authorize_payment,
    capture_payment,
    get_transaction_or_404,
    refund_payment,
)

router = APIRouter(prefix="/payments", tags=["payments"])


def _to_out(transaction) -> TransactionOut:
    return TransactionOut.model_validate(transaction, from_attributes=True)


@router.post("/authorize", response_model=TransactionOut, status_code=201)
async def authorize(
    payload: PaymentAuthorize,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TransactionOut:
    transaction = await authorize_payment(
        session,
        order_id=payload.order_id,
        customer_id=payload.customer_id,
        amount=payload.amount,
        currency=payload.currency,
        payment_method_token=payload.payment_method_token,
        metadata=payload.metadata,
        correlation_id=getattr(request.state, "correlation_id", None),
    )
    return _to_out(transaction)


@router.post("/capture", response_model=TransactionOut)
async def capture(
    payload: PaymentCapture,
    session: AsyncSession = Depends(get_session),
) -> TransactionOut:
    transaction = await get_transaction_or_404(session, payload.transaction_id)
    transaction = await capture_payment(session, transaction, payload.amount)
    return _to_out(transaction)


@router.post("/refund", response_model=TransactionOut)
async def refund(
    payload: PaymentRefund,
    session: AsyncSession = Depends(get_session),
) -> TransactionOut:
    transaction = await get_transaction_or_404(session, payload.transaction_id)
    transaction = await refund_payment(session, transaction, payload.amount, payload.reason)
    return _to_out(transaction)


@router.get("/{transaction_id}", response_model=TransactionOut)
async def get_payment(
    transaction_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> TransactionOut:
    transaction = await get_transaction_or_404(session, transaction_id)
    return _to_out(transaction)
