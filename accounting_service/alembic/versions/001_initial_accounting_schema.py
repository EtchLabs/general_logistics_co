"""Initial accounting schema."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "accounting"


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

    _ensure_enum(
        "account_type",
        ("asset", "liability", "equity", "revenue", "expense"),
    )

    account_type = postgresql.ENUM(
        "asset",
        "liability",
        "equity",
        "revenue",
        "expense",
        name="account_type",
        schema=SCHEMA,
        create_type=False,
    )

    inspector = inspect(op.get_bind())

    if not inspector.has_table("accounts", schema=SCHEMA):
        op.create_table(
            "accounts",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("code", sa.String(20), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("account_type", account_type, nullable=False),
            sa.Column(
                "balance",
                sa.Numeric(14, 2),
                nullable=False,
                server_default="0",
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )
        op.create_index("ix_accounts_code", "accounts", ["code"], unique=True, schema=SCHEMA)

    if not inspector.has_table("journal_entries", schema=SCHEMA):
        op.create_table(
            "journal_entries",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("entry_date", sa.Date(), nullable=False),
            sa.Column("description", sa.String(500), nullable=False),
            sa.Column("reference", sa.String(100)),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )

    if not inspector.has_table("ledger_lines", schema=SCHEMA):
        op.create_table(
            "ledger_lines",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "journal_entry_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.journal_entries.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "account_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.accounts.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("description", sa.String(500)),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_ledger_lines_journal_entry_id",
            "ledger_lines",
            ["journal_entry_id"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_ledger_lines_account_id",
            "ledger_lines",
            ["account_id"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    op.drop_table("ledger_lines", schema=SCHEMA)
    op.drop_table("journal_entries", schema=SCHEMA)
    op.drop_table("accounts", schema=SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.account_type")
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
