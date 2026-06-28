"""Initial customers schema."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "customers"


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

    _ensure_enum("loyalty_tier", ("bronze", "silver", "gold", "platinum"))
    _ensure_enum(
        "ticket_status",
        ("open", "in_progress", "waiting_customer", "resolved", "closed"),
    )
    _ensure_enum("ticket_priority", ("low", "normal", "high", "urgent"))

    loyalty_tier = postgresql.ENUM(
        "bronze",
        "silver",
        "gold",
        "platinum",
        name="loyalty_tier",
        schema=SCHEMA,
        create_type=False,
    )
    ticket_status = postgresql.ENUM(
        "open",
        "in_progress",
        "waiting_customer",
        "resolved",
        "closed",
        name="ticket_status",
        schema=SCHEMA,
        create_type=False,
    )
    ticket_priority = postgresql.ENUM(
        "low",
        "normal",
        "high",
        "urgent",
        name="ticket_priority",
        schema=SCHEMA,
        create_type=False,
    )

    inspector = inspect(op.get_bind())

    if not inspector.has_table("customers", schema=SCHEMA):
        op.create_table(
            "customers",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("first_name", sa.String(100), nullable=False),
            sa.Column("last_name", sa.String(100), nullable=False),
            sa.Column("phone", sa.String(30)),
            sa.Column("loyalty_tier", loyalty_tier, nullable=False, server_default="bronze"),
            sa.Column("is_wholesale", sa.Boolean(), nullable=False, server_default=sa.false()),
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
        op.create_index("ix_customers_email", "customers", ["email"], unique=True, schema=SCHEMA)

    if not inspector.has_table("addresses", schema=SCHEMA):
        op.create_table(
            "addresses",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "customer_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.customers.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("label", sa.String(50), nullable=False, server_default="Home"),
            sa.Column("line1", sa.String(200), nullable=False),
            sa.Column("line2", sa.String(200)),
            sa.Column("city", sa.String(100), nullable=False),
            sa.Column("state", sa.String(50), nullable=False),
            sa.Column("postal_code", sa.String(20), nullable=False),
            sa.Column("country", sa.String(2), nullable=False, server_default="US"),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )
        op.create_index("ix_addresses_customer_id", "addresses", ["customer_id"], schema=SCHEMA)

    if not inspector.has_table("payment_methods", schema=SCHEMA):
        op.create_table(
            "payment_methods",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "customer_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.customers.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("label", sa.String(50), nullable=False, server_default="Card"),
            sa.Column("token", sa.String(100), nullable=False),
            sa.Column("last_four", sa.String(4), nullable=False),
            sa.Column("card_brand", sa.String(20), nullable=False),
            sa.Column("exp_month", sa.Integer(), nullable=False),
            sa.Column("exp_year", sa.Integer(), nullable=False),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_payment_methods_customer_id", "payment_methods", ["customer_id"], schema=SCHEMA
        )

    if not inspector.has_table("support_tickets", schema=SCHEMA):
        op.create_table(
            "support_tickets",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "customer_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.customers.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("subject", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("status", ticket_status, nullable=False, server_default="open"),
            sa.Column("priority", ticket_priority, nullable=False, server_default="normal"),
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
        op.create_index(
            "ix_support_tickets_customer_id", "support_tickets", ["customer_id"], schema=SCHEMA
        )


def downgrade() -> None:
    op.drop_table("support_tickets", schema=SCHEMA)
    op.drop_table("payment_methods", schema=SCHEMA)
    op.drop_table("addresses", schema=SCHEMA)
    op.drop_table("customers", schema=SCHEMA)

    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.ticket_priority")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.ticket_status")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.loyalty_tier")
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
