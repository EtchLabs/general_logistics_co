from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.postgres import (
    GoodsReceipt,
    GoodsReceiptLineItem,
    InvoiceStatus,
    POLineItem,
    POStatus,
    PurchaseOrder,
    ReceiptStatus,
    SupplierInvoice,
    SupplierInvoiceLineItem,
)
from app.models.schemas import DiscrepancyOut, SupplierInvoiceLineItemOut


async def generate_receipt_number(session: AsyncSession) -> str:
    result = await session.execute(select(func.count()).select_from(GoodsReceipt))
    count = result.scalar_one() or 0
    return f"RCV-{count + 1:06d}"


async def generate_invoice_number(session: AsyncSession) -> str:
    result = await session.execute(select(func.count()).select_from(SupplierInvoice))
    count = result.scalar_one() or 0
    return f"INV-{count + 1:06d}"


async def get_invoice_or_404(session: AsyncSession, invoice_id: UUID) -> SupplierInvoice:
    result = await session.execute(
        select(SupplierInvoice)
        .options(
            selectinload(SupplierInvoice.line_items),
            selectinload(SupplierInvoice.purchase_order).selectinload(PurchaseOrder.line_items),
            selectinload(SupplierInvoice.purchase_order).selectinload(PurchaseOrder.receipts).selectinload(
                GoodsReceipt.line_items
            ),
        )
        .where(SupplierInvoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Supplier invoice not found")
    return invoice


def aggregate_received_quantities(receipts: list[GoodsReceipt]) -> dict[str, int]:
    totals: dict[str, int] = defaultdict(int)
    for receipt in receipts:
        for line in receipt.line_items:
            totals[line.sku] += line.quantity_received
    return dict(totals)


def compute_discrepancies(
    po_lines: list[POLineItem],
    receipts: list[GoodsReceipt],
    invoice_lines: list[SupplierInvoiceLineItem],
) -> list[DiscrepancyOut]:
    po_by_sku = {line.sku: line for line in po_lines}
    received_by_sku = aggregate_received_quantities(receipts)
    invoiced_by_sku: dict[str, int] = defaultdict(int)
    for line in invoice_lines:
        invoiced_by_sku[line.sku] += line.quantity

    discrepancies: list[DiscrepancyOut] = []
    for sku, po_line in po_by_sku.items():
        po_qty = po_line.quantity
        received_qty = received_by_sku.get(sku, 0)
        invoiced_qty = invoiced_by_sku.get(sku, 0)
        if received_qty == po_qty and invoiced_qty == po_qty:
            continue
        notes: list[str] = []
        if received_qty != po_qty:
            notes.append(f"PO ordered {po_qty}; received {received_qty}")
        if invoiced_qty != po_qty:
            notes.append(f"Supplier invoiced for {invoiced_qty}; PO ordered {po_qty}")
        if invoiced_qty != received_qty:
            notes.append(f"Supplier invoiced for {invoiced_qty}; only {received_qty} received")
        disc_type = "quantity_mismatch"
        if invoiced_qty != received_qty and received_qty != po_qty:
            disc_type = "quantity_mismatch"
        discrepancies.append(
            DiscrepancyOut(
                type=disc_type,
                sku=sku,
                po_quantity=po_qty,
                received_quantity=received_qty,
                invoiced_quantity=invoiced_qty,
                notes="; ".join(notes),
            )
        )
    return discrepancies


def derive_match_status(
    invoice: SupplierInvoice,
    discrepancies: list[DiscrepancyOut],
) -> str:
    if invoice.status == InvoiceStatus.MATCHED:
        return "matched"
    if invoice.status == InvoiceStatus.DISPUTED:
        return "disputed"
    if invoice.status == InvoiceStatus.PAID:
        return "paid"
    if discrepancies:
        return "discrepancy"
    return "pending_match"


def invoice_line_items_out(invoice: SupplierInvoice) -> list[SupplierInvoiceLineItemOut]:
    return [
        SupplierInvoiceLineItemOut(
            sku=line.sku,
            quantity=line.quantity,
            unit_cost=line.unit_cost,
            line_total=line.line_total,
        )
        for line in invoice.line_items
    ]


async def create_goods_receipt(
    session: AsyncSession,
    po: PurchaseOrder,
    *,
    line_quantities: dict[str, int] | None = None,
    received_at: datetime | None = None,
) -> GoodsReceipt:
    receipt_number = await generate_receipt_number(session)
    receipt = GoodsReceipt(
        purchase_order_id=po.id,
        receipt_number=receipt_number,
        received_at=received_at or datetime.now(UTC),
    )
    session.add(receipt)
    await session.flush()

    all_received = True
    for po_line in po.line_items:
        ordered = po_line.quantity
        received = line_quantities.get(po_line.sku, ordered) if line_quantities else ordered
        received = min(received, ordered)
        if received < ordered:
            all_received = False
        session.add(
            GoodsReceiptLineItem(
                receipt_id=receipt.id,
                sku=po_line.sku,
                quantity_ordered=ordered,
                quantity_received=received,
                unit_cost=po_line.unit_cost,
            )
        )

    receipt.status = ReceiptStatus.COMPLETE if all_received else ReceiptStatus.PARTIAL
    return receipt


async def create_supplier_invoice_for_po(
    session: AsyncSession,
    po: PurchaseOrder,
    *,
    invoice_quantities: dict[str, int] | None = None,
    invoice_date: date | None = None,
) -> SupplierInvoice:
    existing = await session.execute(
        select(SupplierInvoice.id).where(SupplierInvoice.purchase_order_id == po.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Invoice already exists for purchase order")

    invoice_number = await generate_invoice_number(session)
    inv_date = invoice_date or date.today()
    invoice = SupplierInvoice(
        invoice_number=invoice_number,
        supplier_id=po.supplier_id,
        purchase_order_id=po.id,
        status=InvoiceStatus.PENDING_MATCH,
        invoice_date=inv_date,
        due_date=inv_date + timedelta(days=30),
    )
    session.add(invoice)
    await session.flush()

    total = Decimal("0")
    for po_line in po.line_items:
        qty = invoice_quantities.get(po_line.sku, po_line.quantity) if invoice_quantities else po_line.quantity
        line_total = po_line.unit_cost * qty
        total += line_total
        session.add(
            SupplierInvoiceLineItem(
                invoice_id=invoice.id,
                sku=po_line.sku,
                quantity=qty,
                unit_cost=po_line.unit_cost,
                line_total=line_total,
            )
        )

    invoice.total_amount = total

    po_with_receipts = await session.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.line_items),
            selectinload(PurchaseOrder.receipts).selectinload(GoodsReceipt.line_items),
        )
        .where(PurchaseOrder.id == po.id)
    )
    loaded_po = po_with_receipts.scalar_one()
    await session.refresh(invoice, ["line_items"])
    discrepancies = compute_discrepancies(
        loaded_po.line_items,
        loaded_po.receipts,
        invoice.line_items,
    )
    invoice.discrepancies = [d.model_dump() for d in discrepancies]
    return invoice


def po_has_discrepancy(po: PurchaseOrder) -> bool:
    if not po.receipts:
        return False
    received_by_sku = aggregate_received_quantities(po.receipts)
    for line in po.line_items:
        if received_by_sku.get(line.sku, 0) != line.quantity:
            return True
    return False


async def update_po_receipt_status(session: AsyncSession, po: PurchaseOrder) -> None:
    if not po.receipts:
        return
    received_by_sku = aggregate_received_quantities(po.receipts)
    all_complete = all(
        received_by_sku.get(line.sku, 0) >= line.quantity for line in po.line_items
    )
    any_received = any(received_by_sku.get(line.sku, 0) > 0 for line in po.line_items)
    if all_complete:
        po.status = POStatus.RECEIVED
    elif any_received:
        po.status = POStatus.PARTIALLY_RECEIVED
