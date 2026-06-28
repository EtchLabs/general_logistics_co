"""Initial suppliers schema."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
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
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    inspector = inspect(op.get_bind())

    _ensure_enum(
        "po_status",
        ("draft", "submitted", "acknowledged", "partially_received", "received", "cancelled"),
    )

    po_status = postgresql.ENUM(
        "draft",
        "submitted",
        "acknowledged",
        "partially_received",
        "received",
        "cancelled",
        name="po_status",
        schema=SCHEMA,
        create_type=False,
    )

    if not inspector.has_table("suppliers", schema=SCHEMA):
        op.create_table(
            "suppliers",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("contact_email", sa.String(255), nullable=False),
            sa.Column("contact_phone", sa.String(30)),
            sa.Column("payment_terms", sa.String(50), nullable=False, server_default="net_30"),
            sa.Column("lead_time_days", sa.Integer(), nullable=False, server_default="7"),
            sa.Column("reliability_score", sa.Numeric(4, 2), server_default="85.00"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("address_line1", sa.String(200)),
            sa.Column("address_line2", sa.String(200)),
            sa.Column("city", sa.String(100)),
            sa.Column("state", sa.String(50)),
            sa.Column("postal_code", sa.String(20)),
            sa.Column("country", sa.String(2), server_default="US"),
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
        op.create_index("ix_suppliers_name", "suppliers", ["name"], schema=SCHEMA)

    if not inspector.has_table("purchase_orders", schema=SCHEMA):
        op.create_table(
            "purchase_orders",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("po_number", sa.String(30), nullable=False),
            sa.Column(
                "supplier_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.suppliers.id"),
                nullable=False,
            ),
            sa.Column("status", po_status, nullable=False, server_default="draft"),
            sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("expected_delivery_date", sa.Date()),
            sa.Column("notes", sa.Text()),
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
        op.create_index("ix_purchase_orders_po_number", "purchase_orders", ["po_number"], unique=True, schema=SCHEMA)
        op.create_index("ix_purchase_orders_supplier_id", "purchase_orders", ["supplier_id"], schema=SCHEMA)
        op.create_index("ix_purchase_orders_status", "purchase_orders", ["status"], schema=SCHEMA)

    if not inspector.has_table("po_line_items", schema=SCHEMA):
        op.create_table(
            "po_line_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "purchase_order_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.purchase_orders.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sku", sa.String(50), nullable=False),
            sa.Column("product_name", sa.String(200), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("unit_cost", sa.Numeric(12, 2), nullable=False),
            sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_po_line_items_purchase_order_id",
            "po_line_items",
            ["purchase_order_id"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    op.drop_table("po_line_items", schema=SCHEMA)
    op.drop_table("purchase_orders", schema=SCHEMA)
    op.drop_table("suppliers", schema=SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.po_status")
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
