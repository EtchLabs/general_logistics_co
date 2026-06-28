from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.postgres import get_session
from app.models.postgres import InvoiceStatus, SupplierInvoice
from app.models.schemas import (
    InvoiceMatchAction,
    InvoiceMatchResultOut,
    SupplierInvoiceDetailOut,
    SupplierInvoiceOut,
)
from app.services.procurement_service import (
    compute_discrepancies,
    derive_match_status,
    get_invoice_or_404,
    invoice_line_items_out,
)

router = APIRouter(prefix="/supplier-invoices", tags=["supplier-invoices"])


@router.get("", response_model=list[SupplierInvoiceOut])
async def list_supplier_invoices(
    status: InvoiceStatus | None = Query(default=None),
    supplier_id: UUID | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[SupplierInvoiceOut]:
    query = (
        select(SupplierInvoice)
        .options(selectinload(SupplierInvoice.line_items))
        .order_by(SupplierInvoice.invoice_date.desc(), SupplierInvoice.created_at.desc())
    )
    if status:
        query = query.where(SupplierInvoice.status == status)
    if supplier_id:
        query = query.where(SupplierInvoice.supplier_id == supplier_id)
    result = await session.execute(query.offset(offset).limit(limit))
    invoices = result.scalars().all()
    return [
        SupplierInvoiceOut(
            id=inv.id,
            invoice_number=inv.invoice_number,
            supplier_id=inv.supplier_id,
            purchase_order_id=inv.purchase_order_id,
            status=inv.status,
            total_amount=inv.total_amount,
            invoice_date=inv.invoice_date,
            due_date=inv.due_date,
            line_items=invoice_line_items_out(inv),
        )
        for inv in invoices
    ]


@router.get("/{invoice_id}", response_model=SupplierInvoiceDetailOut)
async def get_supplier_invoice(
    invoice_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> SupplierInvoiceDetailOut:
    invoice = await get_invoice_or_404(session, invoice_id)
    po = invoice.purchase_order
    discrepancies = compute_discrepancies(
        po.line_items,
        po.receipts,
        invoice.line_items,
    )
    match_status = derive_match_status(invoice, discrepancies)
    return SupplierInvoiceDetailOut(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        supplier_id=invoice.supplier_id,
        purchase_order_id=invoice.purchase_order_id,
        status=invoice.status,
        total_amount=invoice.total_amount,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        line_items=invoice_line_items_out(invoice),
        match_status=match_status,
        discrepancies=discrepancies,
        match_notes=invoice.match_notes,
    )


@router.post("/{invoice_id}/match", response_model=InvoiceMatchResultOut)
async def match_supplier_invoice(
    invoice_id: UUID,
    payload: InvoiceMatchAction,
    session: AsyncSession = Depends(get_session),
) -> InvoiceMatchResultOut:
    invoice = await get_invoice_or_404(session, invoice_id)
    if payload.action == "approve":
        invoice.status = InvoiceStatus.MATCHED
    elif payload.action == "hold":
        invoice.status = InvoiceStatus.PENDING_MATCH
    elif payload.action == "dispute":
        invoice.status = InvoiceStatus.DISPUTED
    else:
        raise HTTPException(status_code=400, detail="Invalid match action")

    if payload.notes:
        invoice.match_notes = payload.notes

    po = invoice.purchase_order
    discrepancies = compute_discrepancies(
        po.line_items,
        po.receipts,
        invoice.line_items,
    )
    invoice.discrepancies = [d.model_dump() for d in discrepancies]
    await session.commit()
    await session.refresh(invoice)

    return InvoiceMatchResultOut(
        id=invoice.id,
        status=invoice.status,
        match_status=derive_match_status(invoice, discrepancies),
        match_notes=invoice.match_notes,
    )
