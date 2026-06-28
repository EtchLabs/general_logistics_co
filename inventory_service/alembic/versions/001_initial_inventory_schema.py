"""Initial inventory schema."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "inventory"


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

    _ensure_enum("reservation_status", ("active", "released", "fulfilled"))
    _ensure_enum(
        "movement_type",
        ("receive", "adjust", "reserve", "release", "ship", "damage"),
    )

    reservation_status = postgresql.ENUM(
        "active",
        "released",
        "fulfilled",
        name="reservation_status",
        schema=SCHEMA,
        create_type=False,
    )
    movement_type = postgresql.ENUM(
        "receive",
        "adjust",
        "reserve",
        "release",
        "ship",
        "damage",
        name="movement_type",
        schema=SCHEMA,
        create_type=False,
    )

    if not inspector.has_table("fulfillment_centers", schema=SCHEMA):
        op.create_table(
            "fulfillment_centers",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("code", sa.String(20), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("line1", sa.String(200), nullable=False),
            sa.Column("city", sa.String(100), nullable=False),
            sa.Column("state", sa.String(50), nullable=False),
            sa.Column("postal_code", sa.String(20), nullable=False),
            sa.Column("country", sa.String(2), nullable=False, server_default="US"),
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
        op.create_index(
            "ix_fulfillment_centers_code",
            "fulfillment_centers",
            ["code"],
            unique=True,
            schema=SCHEMA,
        )

    if not inspector.has_table("sku_stock", schema=SCHEMA):
        op.create_table(
            "sku_stock",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "fulfillment_center_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.fulfillment_centers.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("sku", sa.String(50), nullable=False),
            sa.Column("on_hand", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("reserved", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("reorder_point", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.UniqueConstraint("fulfillment_center_id", "sku", name="uq_sku_stock_fc_sku"),
            schema=SCHEMA,
        )
        op.create_index("ix_sku_stock_fc_id", "sku_stock", ["fulfillment_center_id"], schema=SCHEMA)
        op.create_index("ix_sku_stock_sku", "sku_stock", ["sku"], schema=SCHEMA)

    if not inspector.has_table("reservations", schema=SCHEMA):
        op.create_table(
            "reservations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("sku", sa.String(50), nullable=False),
            sa.Column(
                "fulfillment_center_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.fulfillment_centers.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column(
                "status",
                reservation_status,
                nullable=False,
                server_default="active",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("released_at", sa.DateTime(timezone=True)),
            schema=SCHEMA,
        )
        op.create_index("ix_reservations_order_id", "reservations", ["order_id"], schema=SCHEMA)
        op.create_index("ix_reservations_sku", "reservations", ["sku"], schema=SCHEMA)
        op.create_index(
            "ix_reservations_fc_id", "reservations", ["fulfillment_center_id"], schema=SCHEMA
        )

    if not inspector.has_table("stock_movements", schema=SCHEMA):
        op.create_table(
            "stock_movements",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("sku", sa.String(50), nullable=False),
            sa.Column(
                "fulfillment_center_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.fulfillment_centers.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("movement_type", movement_type, nullable=False),
            sa.Column("quantity_delta", sa.Integer(), nullable=False),
            sa.Column("reference_type", sa.String(50)),
            sa.Column("reference_id", postgresql.UUID(as_uuid=True)),
            sa.Column("notes", sa.Text()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )
        op.create_index("ix_stock_movements_sku", "stock_movements", ["sku"], schema=SCHEMA)
        op.create_index(
            "ix_stock_movements_fc_id", "stock_movements", ["fulfillment_center_id"], schema=SCHEMA
        )


def downgrade() -> None:
    op.drop_table("stock_movements", schema=SCHEMA)
    op.drop_table("reservations", schema=SCHEMA)
    op.drop_table("sku_stock", schema=SCHEMA)
    op.drop_table("fulfillment_centers", schema=SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.movement_type")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.reservation_status")
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
