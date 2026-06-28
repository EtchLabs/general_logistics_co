"""Initial payments schema."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "payments"


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
        "transaction_status",
        ("pending", "authorized", "captured", "refunded", "partially_refunded", "failed"),
    )

    transaction_status = postgresql.ENUM(
        "pending",
        "authorized",
        "captured",
        "refunded",
        "partially_refunded",
        "failed",
        name="transaction_status",
        schema=SCHEMA,
        create_type=False,
    )

    if not inspector.has_table("transactions", schema=SCHEMA):
        op.create_table(
            "transactions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("status", transaction_status, nullable=False, server_default="pending"),
            sa.Column("payment_method_token", sa.String(100), nullable=False),
            sa.Column("processor_ref", sa.String(100)),
            sa.Column("authorized_amount", sa.Numeric(12, 2), server_default="0"),
            sa.Column("captured_amount", sa.Numeric(12, 2), server_default="0"),
            sa.Column("refunded_amount", sa.Numeric(12, 2), server_default="0"),
            sa.Column("correlation_id", sa.String(64)),
            sa.Column(
                "metadata",
                postgresql.JSONB,
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
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
        op.create_index("ix_transactions_order_id", "transactions", ["order_id"], schema=SCHEMA)
        op.create_index("ix_transactions_customer_id", "transactions", ["customer_id"], schema=SCHEMA)
        op.create_index("ix_transactions_status", "transactions", ["status"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("transactions", schema=SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.transaction_status")
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
