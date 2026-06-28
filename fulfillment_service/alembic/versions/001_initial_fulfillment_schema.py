"""Initial fulfillment schema."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "fulfillment"


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
        "fulfillment_job_status",
        ("queued", "pick", "pack", "ready_to_ship", "completed", "cancelled"),
    )

    fulfillment_job_status = postgresql.ENUM(
        "queued",
        "pick",
        "pack",
        "ready_to_ship",
        "completed",
        "cancelled",
        name="fulfillment_job_status",
        schema=SCHEMA,
        create_type=False,
    )

    if not inspector.has_table("fulfillment_jobs", schema=SCHEMA):
        op.create_table(
            "fulfillment_jobs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("fulfillment_center_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "status",
                fulfillment_job_status,
                nullable=False,
                server_default="queued",
            ),
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
            "ix_fulfillment_jobs_order_id", "fulfillment_jobs", ["order_id"], schema=SCHEMA
        )
        op.create_index(
            "ix_fulfillment_jobs_fc_id",
            "fulfillment_jobs",
            ["fulfillment_center_id"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_fulfillment_jobs_status", "fulfillment_jobs", ["status"], schema=SCHEMA
        )

    if not inspector.has_table("pick_lists", schema=SCHEMA):
        op.create_table(
            "pick_lists",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "fulfillment_job_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.fulfillment_jobs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("line_items", postgresql.JSONB, nullable=False),
            sa.Column("picker_id", sa.String(50)),
            sa.Column("picked_quantity", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_pick_lists_job_id", "pick_lists", ["fulfillment_job_id"], schema=SCHEMA
        )


def downgrade() -> None:
    op.drop_table("pick_lists", schema=SCHEMA)
    op.drop_table("fulfillment_jobs", schema=SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.fulfillment_job_status")
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
