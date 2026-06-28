from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.postgres import get_session
from app.models.postgres import GoodsReceipt, POStatus, POLineItem, PurchaseOrder, Supplier, SupplierInvoice
from app.models.schemas import (
    GoodsReceiptOut,
    PurchaseOrderCreate,
    PurchaseOrderOut,
    PurchaseOrderUpdate,
    POShipmentCreate,
    ReceiptLineItemOut,
    SupplierCreate,
    SupplierOut,
    SupplierUpdate,
)
from app.services.procurement_service import (
    create_goods_receipt,
    create_supplier_invoice_for_po,
    po_has_discrepancy,
    update_po_receipt_status,
)
from app.services.supplier_service import (
    create_purchase_order,
    get_purchase_order_or_404,
    get_supplier_or_404,
)

router = APIRouter(tags=["suppliers"])


@router.post("/suppliers", response_model=SupplierOut, status_code=201)
async def create_supplier(
    payload: SupplierCreate,
    session: AsyncSession = Depends(get_session),
) -> SupplierOut:
    supplier = Supplier(**payload.model_dump())
    session.add(supplier)
    await session.commit()
    await session.refresh(supplier)
    return SupplierOut.model_validate(supplier)


@router.get("/suppliers", response_model=list[SupplierOut])
async def list_suppliers(
    active_only: bool = Query(default=True),
    session: AsyncSession = Depends(get_session),
) -> list[SupplierOut]:
    query = select(Supplier).order_by(Supplier.name)
    if active_only:
        query = query.where(Supplier.is_active.is_(True))
    result = await session.execute(query)
    return [SupplierOut.model_validate(s) for s in result.scalars().all()]


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut)
async def get_supplier(
    supplier_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> SupplierOut:
    supplier = await get_supplier_or_404(session, supplier_id)
    return SupplierOut.model_validate(supplier)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut)
async def update_supplier(
    supplier_id: UUID,
    payload: SupplierUpdate,
    session: AsyncSession = Depends(get_session),
) -> SupplierOut:
    supplier = await get_supplier_or_404(session, supplier_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(supplier, field, value)
    await session.commit()
    await session.refresh(supplier)
    return SupplierOut.model_validate(supplier)


@router.delete("/suppliers/{supplier_id}", status_code=204)
async def delete_supplier(
    supplier_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    supplier = await get_supplier_or_404(session, supplier_id)
    po_result = await session.execute(
        select(PurchaseOrder.id).where(
            PurchaseOrder.supplier_id == supplier_id,
            PurchaseOrder.status.not_in([POStatus.CANCELLED, POStatus.RECEIVED]),
        )
    )
    if po_result.first():
        raise HTTPException(
            status_code=409,
            detail="Cannot delete supplier with open purchase orders",
        )
    supplier.is_active = False
    await session.commit()


@router.post("/purchase-orders", response_model=PurchaseOrderOut, status_code=201)
async def create_po(
    payload: PurchaseOrderCreate,
    session: AsyncSession = Depends(get_session),
) -> PurchaseOrderOut:
    po = await create_purchase_order(
        session,
        supplier_id=payload.supplier_id,
        line_items=[item.model_dump() for item in payload.line_items],
        expected_delivery_date=payload.expected_delivery_date,
        notes=payload.notes,
        submit=payload.submit,
    )
    return PurchaseOrderOut.model_validate(po)


@router.get("/purchase-orders", response_model=list[PurchaseOrderOut])
async def list_purchase_orders(
    supplier_id: UUID | None = Query(default=None),
    status: POStatus | None = Query(default=None),
    sku: str | None = Query(default=None),
    has_discrepancy: bool | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[PurchaseOrderOut]:
    query = (
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.line_items),
            selectinload(PurchaseOrder.receipts).selectinload(GoodsReceipt.line_items),
        )
        .order_by(PurchaseOrder.created_at.desc())
    )
    if supplier_id:
        query = query.where(PurchaseOrder.supplier_id == supplier_id)
    if status:
        query = query.where(PurchaseOrder.status == status)
    if sku:
        query = query.join(POLineItem).where(POLineItem.sku == sku)
    result = await session.execute(query.offset(offset).limit(limit))
    pos = list(result.scalars().unique().all())
    if has_discrepancy is not None:
        pos = [po for po in pos if po_has_discrepancy(po) == has_discrepancy]
    return [PurchaseOrderOut.model_validate(po) for po in pos]


@router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderOut)
async def get_po(
    po_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> PurchaseOrderOut:
    po = await get_purchase_order_or_404(session, po_id)
    return PurchaseOrderOut.model_validate(po)


@router.patch("/purchase-orders/{po_id}", response_model=PurchaseOrderOut)
async def update_po(
    po_id: UUID,
    payload: PurchaseOrderUpdate,
    session: AsyncSession = Depends(get_session),
) -> PurchaseOrderOut:
    po = await get_purchase_order_or_404(session, po_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(po, field, value)
    await session.commit()
    po = await get_purchase_order_or_404(session, po_id)
    return PurchaseOrderOut.model_validate(po)


@router.get("/purchase-orders/{po_id}/receipts", response_model=list[GoodsReceiptOut])
async def list_po_receipts(
    po_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[GoodsReceiptOut]:
    po = await get_purchase_order_or_404(session, po_id)
    return [
        GoodsReceiptOut(
            id=receipt.id,
            purchase_order_id=receipt.purchase_order_id,
            receipt_number=receipt.receipt_number,
            received_at=receipt.received_at,
            status=receipt.status,
            line_items=[
                ReceiptLineItemOut(
                    sku=line.sku,
                    quantity_ordered=line.quantity_ordered,
                    quantity_received=line.quantity_received,
                    unit_cost=line.unit_cost,
                )
                for line in receipt.line_items
            ],
        )
        for receipt in sorted(po.receipts, key=lambda r: r.received_at, reverse=True)
    ]


@router.post("/purchase-orders/{po_id}/shipments", status_code=204)
async def ship_po(
    po_id: UUID,
    payload: POShipmentCreate,
    session: AsyncSession = Depends(get_session),
) -> None:
    po = await get_purchase_order_or_404(session, po_id)
    line_quantities: dict[str, int] = {}
    for item in payload.line_items:
        sku = item.get("sku")
        if not sku:
            continue
        shipped = item.get("quantity_shipped") or item.get("quantity_received") or item.get("quantity")
        if shipped is not None:
            line_quantities[sku] = int(shipped)

    received_at = payload.shipped_at or None
    receipt = await create_goods_receipt(
        session,
        po,
        line_quantities=line_quantities or None,
        received_at=received_at,
    )
    await update_po_receipt_status(session, po)

    note = f"Shipped {payload.tracking_number}; receipt {receipt.receipt_number}"
    po.notes = f"{po.notes or ''}\n{note}".strip()

    existing_invoice = await session.execute(
        select(SupplierInvoice.id).where(SupplierInvoice.purchase_order_id == po.id)
    )
    if existing_invoice.scalar_one_or_none() is None:
        invoice_quantities = {line.sku: line.quantity for line in po.line_items}
        await create_supplier_invoice_for_po(session, po, invoice_quantities=invoice_quantities)

    await session.commit()
