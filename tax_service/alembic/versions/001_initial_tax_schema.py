"""Initial tax schema."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "tax"


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

    _ensure_enum("ledger_status", ("collected", "remitted"))

    ledger_status = postgresql.ENUM(
        "collected",
        "remitted",
        name="ledger_status",
        schema=SCHEMA,
        create_type=False,
    )

    if not inspector.has_table("tax_rates", schema=SCHEMA):
        op.create_table(
            "tax_rates",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("jurisdiction", sa.String(100), nullable=False),
            sa.Column("state", sa.String(2), nullable=False),
            sa.Column("product_category", sa.String(50), nullable=False, server_default="general"),
            sa.Column("rate_percent", sa.Numeric(6, 4), nullable=False),
            sa.Column("effective_from", sa.Date(), nullable=False),
            sa.Column("effective_to", sa.Date()),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_tax_rates_jurisdiction_category",
            "tax_rates",
            ["jurisdiction", "product_category"],
            schema=SCHEMA,
        )

    if not inspector.has_table("tax_collected_ledger", schema=SCHEMA):
        op.create_table(
            "tax_collected_ledger",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("jurisdiction", sa.String(100), nullable=False),
            sa.Column(
                "tax_rate_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.tax_rates.id"),
                nullable=False,
            ),
            sa.Column("taxable_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False),
            sa.Column("status", ledger_status, nullable=False, server_default="collected"),
            sa.Column("remittance_id", postgresql.UUID(as_uuid=True)),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_tax_collected_ledger_order_id",
            "tax_collected_ledger",
            ["order_id"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_tax_collected_ledger_status",
            "tax_collected_ledger",
            ["status"],
            schema=SCHEMA,
        )

    op.execute(
        f"""
        INSERT INTO {SCHEMA}.tax_rates (id, jurisdiction, state, product_category, rate_percent, effective_from, is_active)
        SELECT gen_random_uuid(), 'US-CA', 'CA', 'general', 7.2500, CURRENT_DATE, true
        WHERE NOT EXISTS (SELECT 1 FROM {SCHEMA}.tax_rates WHERE jurisdiction = 'US-CA' AND product_category = 'general')
        """
    )
    op.execute(
        f"""
        INSERT INTO {SCHEMA}.tax_rates (id, jurisdiction, state, product_category, rate_percent, effective_from, is_active)
        SELECT gen_random_uuid(), 'US-NY', 'NY', 'general', 8.0000, CURRENT_DATE, true
        WHERE NOT EXISTS (SELECT 1 FROM {SCHEMA}.tax_rates WHERE jurisdiction = 'US-NY' AND product_category = 'general')
        """
    )
    op.execute(
        f"""
        INSERT INTO {SCHEMA}.tax_rates (id, jurisdiction, state, product_category, rate_percent, effective_from, is_active)
        SELECT gen_random_uuid(), 'US-TX', 'TX', 'general', 6.2500, CURRENT_DATE, true
        WHERE NOT EXISTS (SELECT 1 FROM {SCHEMA}.tax_rates WHERE jurisdiction = 'US-TX' AND product_category = 'general')
        """
    )


def downgrade() -> None:
    op.drop_table("tax_collected_ledger", schema=SCHEMA)
    op.drop_table("tax_rates", schema=SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.ledger_status")
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
