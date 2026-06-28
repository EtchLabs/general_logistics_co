"""Initial shipping schema."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "shipping"


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

    _ensure_enum("shipment_status", ("label_created", "in_transit", "delivered", "exception"))

    shipment_status = postgresql.ENUM(
        "label_created",
        "in_transit",
        "delivered",
        "exception",
        name="shipment_status",
        schema=SCHEMA,
        create_type=False,
    )

    if not inspector.has_table("shipments", schema=SCHEMA):
        op.create_table(
            "shipments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("fulfillment_job_id", postgresql.UUID(as_uuid=True)),
            sa.Column("carrier", sa.String(50), nullable=False),
            sa.Column("service_level", sa.String(50), nullable=False),
            sa.Column("tracking_number", sa.String(50), nullable=False),
            sa.Column("label_url", sa.String(500), nullable=False),
            sa.Column("weight_oz", sa.Numeric(10, 2), nullable=False),
            sa.Column("shipping_cost", sa.Numeric(12, 2), nullable=False),
            sa.Column(
                "status",
                shipment_status,
                nullable=False,
                server_default="label_created",
            ),
            sa.Column("ship_to_address", postgresql.JSONB, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )
        op.create_index("ix_shipments_order_id", "shipments", ["order_id"], schema=SCHEMA)
        op.create_index(
            "ix_shipments_fulfillment_job_id", "shipments", ["fulfillment_job_id"], schema=SCHEMA
        )
        op.create_index(
            "ix_shipments_tracking_number",
            "shipments",
            ["tracking_number"],
            unique=True,
            schema=SCHEMA,
        )
        op.create_index("ix_shipments_status", "shipments", ["status"], schema=SCHEMA)

    if not inspector.has_table("tracking_events", schema=SCHEMA):
        op.create_table(
            "tracking_events",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "shipment_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.shipments.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("event_type", sa.String(50), nullable=False),
            sa.Column("location", sa.String(100)),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column(
                "occurred_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_tracking_events_shipment_id", "tracking_events", ["shipment_id"], schema=SCHEMA
        )


def downgrade() -> None:
    op.drop_table("tracking_events", schema=SCHEMA)
    op.drop_table("shipments", schema=SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.shipment_status")
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
