from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.postgres import GoodsReceipt, POLineItem, POStatus, PurchaseOrder, Supplier


async def get_supplier_or_404(session: AsyncSession, supplier_id: UUID) -> Supplier:
    result = await session.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


async def get_purchase_order_or_404(session: AsyncSession, po_id: UUID) -> PurchaseOrder:
    result = await session.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.line_items),
            selectinload(PurchaseOrder.receipts).selectinload(GoodsReceipt.line_items),
        )
        .where(PurchaseOrder.id == po_id)
    )
    po = result.scalar_one_or_none()
    if po is None:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    return po


async def generate_po_number(session: AsyncSession) -> str:
    result = await session.execute(select(func.count()).select_from(PurchaseOrder))
    count = result.scalar_one() or 0
    return f"PO-{count + 1:06d}"


async def create_purchase_order(
    session: AsyncSession,
    supplier_id: UUID,
    line_items: list[dict],
    expected_delivery_date,
    notes: str | None,
    submit: bool,
) -> PurchaseOrder:
    await get_supplier_or_404(session, supplier_id)

    po_number = await generate_po_number(session)
    total = Decimal("0")
    po = PurchaseOrder(
        po_number=po_number,
        supplier_id=supplier_id,
        status=POStatus.SUBMITTED if submit else POStatus.DRAFT,
        expected_delivery_date=expected_delivery_date,
        notes=notes,
    )
    session.add(po)
    await session.flush()

    for item in line_items:
        qty = item["quantity"]
        unit_cost = Decimal(str(item["unit_cost"]))
        line_total = unit_cost * qty
        total += line_total
        session.add(
            POLineItem(
                purchase_order_id=po.id,
                sku=item["sku"],
                product_name=item["product_name"],
                quantity=qty,
                unit_cost=unit_cost,
                line_total=line_total,
            )
        )

    po.total_amount = total
    await session.commit()
    return await get_purchase_order_or_404(session, po.id)
