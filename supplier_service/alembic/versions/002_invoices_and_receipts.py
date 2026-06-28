"""Supplier invoices and goods receipts."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "suppliers"


def _ensure_enum(name: str, values: tuple[str, ...]) -> None:
    values_sql = ", ".join(f"'{value}'" for value in values)
    op.execute(
        f"""
        DO $$ BEGIN
            CREATE TYPE {SCHEMA}.{name} AS ENUM ({values_sql});
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    )


def upgrade() -> None:
    inspector = inspect(op.get_bind())

    _ensure_enum(
        "invoice_status",
        ("pending", "pending_match", "matched", "disputed", "paid"),
    )
    _ensure_enum(
        "receipt_status",
        ("partial", "complete"),
    )

    invoice_status = postgresql.ENUM(
        "pending",
        "pending_match",
        "matched",
        "disputed",
        "paid",
        name="invoice_status",
        schema=SCHEMA,
        create_type=False,
    )
    receipt_status = postgresql.ENUM(
        "partial",
        "complete",
        name="receipt_status",
        schema=SCHEMA,
        create_type=False,
    )

    if not inspector.has_table("goods_receipts", schema=SCHEMA):
        op.create_table(
            "goods_receipts",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "purchase_order_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.purchase_orders.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("receipt_number", sa.String(30), nullable=False),
            sa.Column(
                "received_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("status", receipt_status, nullable=False, server_default="partial"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_goods_receipts_purchase_order_id",
            "goods_receipts",
            ["purchase_order_id"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_goods_receipts_receipt_number",
            "goods_receipts",
            ["receipt_number"],
            unique=True,
            schema=SCHEMA,
        )

    if not inspector.has_table("goods_receipt_line_items", schema=SCHEMA):
        op.create_table(
            "goods_receipt_line_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "receipt_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.goods_receipts.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sku", sa.String(50), nullable=False),
            sa.Column("quantity_ordered", sa.Integer(), nullable=False),
            sa.Column("quantity_received", sa.Integer(), nullable=False),
            sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_goods_receipt_line_items_receipt_id",
            "goods_receipt_line_items",
            ["receipt_id"],
            schema=SCHEMA,
        )

    if not inspector.has_table("supplier_invoices", schema=SCHEMA):
        op.create_table(
            "supplier_invoices",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("invoice_number", sa.String(30), nullable=False),
            sa.Column(
                "supplier_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.suppliers.id"),
                nullable=False,
            ),
            sa.Column(
                "purchase_order_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.purchase_orders.id"),
                nullable=False,
            ),
            sa.Column("status", invoice_status, nullable=False, server_default="pending_match"),
            sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("invoice_date", sa.Date(), nullable=False),
            sa.Column("due_date", sa.Date(), nullable=False),
            sa.Column("match_notes", sa.Text()),
            sa.Column("discrepancies", postgresql.JSONB(), nullable=False, server_default="[]"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_supplier_invoices_invoice_number",
            "supplier_invoices",
            ["invoice_number"],
            unique=True,
            schema=SCHEMA,
        )
        op.create_index(
            "ix_supplier_invoices_supplier_id",
            "supplier_invoices",
            ["supplier_id"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_supplier_invoices_purchase_order_id",
            "supplier_invoices",
            ["purchase_order_id"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_supplier_invoices_status",
            "supplier_invoices",
            ["status"],
            schema=SCHEMA,
        )

    if not inspector.has_table("supplier_invoice_line_items", schema=SCHEMA):
        op.create_table(
            "supplier_invoice_line_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "invoice_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.supplier_invoices.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sku", sa.String(50), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
            sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_supplier_invoice_line_items_invoice_id",
            "supplier_invoice_line_items",
            ["invoice_id"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    op.drop_table("supplier_invoice_line_items", schema=SCHEMA)
    op.drop_table("supplier_invoices", schema=SCHEMA)
    op.drop_table("goods_receipt_line_items", schema=SCHEMA)
    op.drop_table("goods_receipts", schema=SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.invoice_status")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.receipt_status")
