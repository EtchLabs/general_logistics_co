"""Initial orders schema."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "orders"


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

    _ensure_enum("order_type", ("b2c", "wholesale"))
    _ensure_enum(
        "order_status",
        ("pending", "confirmed", "in_fulfillment", "shipped", "delivered", "closed", "cancelled"),
    )
    _ensure_enum("payment_status", ("pending", "authorized", "captured", "refunded", "failed"))

    order_type = postgresql.ENUM("b2c", "wholesale", name="order_type", schema=SCHEMA, create_type=False)
    order_status = postgresql.ENUM(
        "pending",
        "confirmed",
        "in_fulfillment",
        "shipped",
        "delivered",
        "closed",
        "cancelled",
        name="order_status",
        schema=SCHEMA,
        create_type=False,
    )
    payment_status = postgresql.ENUM(
        "pending",
        "authorized",
        "captured",
        "refunded",
        "failed",
        name="payment_status",
        schema=SCHEMA,
        create_type=False,
    )

    if not inspector.has_table("orders", schema=SCHEMA):
        op.create_table(
            "orders",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("order_type", order_type, nullable=False, server_default="b2c"),
            sa.Column("status", order_status, nullable=False, server_default="pending"),
            sa.Column("payment_status", payment_status, nullable=False, server_default="pending"),
            sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
            sa.Column("tax_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("shipping_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("discount_total", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("grand_total", sa.Numeric(12, 2), nullable=False),
            sa.Column("coupon_code", sa.String(50)),
            sa.Column("shipping_address", postgresql.JSONB, nullable=False),
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
            sa.Column("closed_at", sa.DateTime(timezone=True)),
            schema=SCHEMA,
        )
        op.create_index("ix_orders_customer_id", "orders", ["customer_id"], schema=SCHEMA)
        op.create_index("ix_orders_status", "orders", ["status"], schema=SCHEMA)

    if not inspector.has_table("order_line_items", schema=SCHEMA):
        op.create_table(
            "order_line_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "order_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.orders.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sku", sa.String(50), nullable=False),
            sa.Column("product_name", sa.String(200), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
            sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
            schema=SCHEMA,
        )
        op.create_index("ix_order_line_items_order_id", "order_line_items", ["order_id"], schema=SCHEMA)

    if not inspector.has_table("order_events", schema=SCHEMA):
        op.create_table(
            "order_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "order_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.orders.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("event_type", sa.String(80), nullable=False),
            sa.Column("from_status", sa.String(30)),
            sa.Column("to_status", sa.String(30)),
            sa.Column("details", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )
        op.create_index("ix_order_events_order_id", "order_events", ["order_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("order_events", schema=SCHEMA)
    op.drop_table("order_line_items", schema=SCHEMA)
    op.drop_table("orders", schema=SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.payment_status")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.order_status")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.order_type")
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
