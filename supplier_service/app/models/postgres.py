import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import get_settings

SCHEMA = get_settings().postgres_schema


class Base(DeclarativeBase):
    pass


class POStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PENDING_MATCH = "pending_match"
    MATCHED = "matched"
    DISPUTED = "disputed"
    PAID = "paid"


class ReceiptStatus(str, enum.Enum):
    PARTIAL = "partial"
    COMPLETE = "complete"


class Supplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str | None] = mapped_column(String(30))
    payment_terms: Mapped[str] = mapped_column(String(50), default="net_30", nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    reliability_score: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("85.00"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    address_line1: Mapped[str | None] = mapped_column(String(200))
    address_line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(50))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(2), default="US")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(back_populates="supplier")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    po_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.suppliers.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[POStatus] = mapped_column(
        Enum(
            POStatus,
            name="po_status",
            schema=SCHEMA,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=POStatus.DRAFT,
        nullable=False,
        index=True,
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    supplier: Mapped["Supplier"] = relationship(back_populates="purchase_orders")
    line_items: Mapped[list["POLineItem"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )
    receipts: Mapped[list["GoodsReceipt"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )
    invoices: Mapped[list["SupplierInvoice"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan"
    )


class POLineItem(Base):
    __tablename__ = "po_line_items"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="line_items")


class GoodsReceipt(Base):
    __tablename__ = "goods_receipts"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    receipt_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[ReceiptStatus] = mapped_column(
        Enum(
            ReceiptStatus,
            name="receipt_status",
            schema=SCHEMA,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ReceiptStatus.PARTIAL,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="receipts")
    line_items: Mapped[list["GoodsReceiptLineItem"]] = relationship(
        back_populates="receipt", cascade="all, delete-orphan"
    )


class GoodsReceiptLineItem(Base):
    __tablename__ = "goods_receipt_line_items"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.goods_receipts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    receipt: Mapped["GoodsReceipt"] = relationship(back_populates="line_items")


class SupplierInvoice(Base):
    __tablename__ = "supplier_invoices"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_number: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.suppliers.id"),
        nullable=False,
        index=True,
    )
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.purchase_orders.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(
            InvoiceStatus,
            name="invoice_status",
            schema=SCHEMA,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=InvoiceStatus.PENDING_MATCH,
        nullable=False,
        index=True,
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    match_notes: Mapped[str | None] = mapped_column(Text)
    discrepancies: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    supplier: Mapped["Supplier"] = relationship()
    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="invoices")
    line_items: Mapped[list["SupplierInvoiceLineItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )


class SupplierInvoiceLineItem(Base):
    __tablename__ = "supplier_invoice_line_items"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.supplier_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    invoice: Mapped["SupplierInvoice"] = relationship(back_populates="line_items")
