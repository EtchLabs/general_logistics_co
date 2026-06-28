"""Initial products_pricing schema."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "products_pricing"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    inspector = inspect(op.get_bind())

    if not inspector.has_table("sku_pricing", schema=SCHEMA):
        op.create_table(
            "sku_pricing",
            sa.Column("sku", sa.String(50), primary_key=True),
            sa.Column("msrp", sa.Numeric(12, 2), nullable=False),
            sa.Column("sale_price", sa.Numeric(12, 2)),
            sa.Column("cost_basis", sa.Numeric(12, 2), nullable=False),
            sa.Column("supplier_id", postgresql.UUID(as_uuid=True)),
            sa.Column("reorder_threshold", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sale_starts_at", sa.DateTime(timezone=True)),
            sa.Column("sale_ends_at", sa.DateTime(timezone=True)),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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

    if not inspector.has_table("bulk_discount_tiers", schema=SCHEMA):
        op.create_table(
            "bulk_discount_tiers",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("sku", sa.String(50), nullable=False),
            sa.Column("min_quantity", sa.Integer(), nullable=False),
            sa.Column("discount_percent", sa.Numeric(5, 2), nullable=False),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_bulk_discount_tiers_sku", "bulk_discount_tiers", ["sku"], schema=SCHEMA
        )

    if not inspector.has_table("promotions", schema=SCHEMA):
        op.create_table(
            "promotions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("discount_type", sa.String(20), nullable=False),
            sa.Column("discount_value", sa.Numeric(12, 2), nullable=False),
            sa.Column("starts_at", sa.DateTime(timezone=True)),
            sa.Column("ends_at", sa.DateTime(timezone=True)),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )

    if not inspector.has_table("coupon_codes", schema=SCHEMA):
        op.create_table(
            "coupon_codes",
            sa.Column("code", sa.String(50), primary_key=True),
            sa.Column(
                "promotion_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.promotions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("max_uses", sa.Integer()),
            sa.Column("current_uses", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )


def downgrade() -> None:
    op.drop_table("coupon_codes", schema=SCHEMA)
    op.drop_table("promotions", schema=SCHEMA)
    op.drop_table("bulk_discount_tiers", schema=SCHEMA)
    op.drop_table("sku_pricing", schema=SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
