"""Initial hr_payroll schema."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "hr_payroll"


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

    _ensure_enum("employment_type", ("full_time", "part_time", "contractor"))
    _ensure_enum("payroll_run_status", ("draft", "processing", "completed", "failed"))

    employment_type = postgresql.ENUM(
        "full_time",
        "part_time",
        "contractor",
        name="employment_type",
        schema=SCHEMA,
        create_type=False,
    )
    payroll_run_status = postgresql.ENUM(
        "draft",
        "processing",
        "completed",
        "failed",
        name="payroll_run_status",
        schema=SCHEMA,
        create_type=False,
    )

    inspector = inspect(op.get_bind())

    if not inspector.has_table("departments", schema=SCHEMA):
        op.create_table(
            "departments",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("code", sa.String(20), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )
        op.create_index("ix_departments_code", "departments", ["code"], unique=True, schema=SCHEMA)

    if not inspector.has_table("employees", schema=SCHEMA):
        op.create_table(
            "employees",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "department_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.departments.id", ondelete="SET NULL"),
            ),
            sa.Column("first_name", sa.String(100), nullable=False),
            sa.Column("last_name", sa.String(100), nullable=False),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("hire_date", sa.Date(), nullable=False),
            sa.Column(
                "employment_type",
                employment_type,
                nullable=False,
                server_default="full_time",
            ),
            sa.Column("salary", sa.Numeric(12, 2)),
            sa.Column("hourly_rate", sa.Numeric(8, 2)),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )
        op.create_index("ix_employees_email", "employees", ["email"], unique=True, schema=SCHEMA)
        op.create_index("ix_employees_department_id", "employees", ["department_id"], schema=SCHEMA)

    if not inspector.has_table("payroll_runs", schema=SCHEMA):
        op.create_table(
            "payroll_runs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("period_end", sa.Date(), nullable=False),
            sa.Column(
                "status",
                payroll_run_status,
                nullable=False,
                server_default="draft",
            ),
            sa.Column(
                "total_gross",
                sa.Numeric(14, 2),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "total_net",
                sa.Numeric(14, 2),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            schema=SCHEMA,
        )

    if not inspector.has_table("pay_stubs", schema=SCHEMA):
        op.create_table(
            "pay_stubs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "payroll_run_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.payroll_runs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "employee_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{SCHEMA}.employees.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("gross_pay", sa.Numeric(12, 2), nullable=False),
            sa.Column("deductions", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("net_pay", sa.Numeric(12, 2), nullable=False),
            schema=SCHEMA,
        )
        op.create_index(
            "ix_pay_stubs_payroll_run_id",
            "pay_stubs",
            ["payroll_run_id"],
            schema=SCHEMA,
        )
        op.create_index(
            "ix_pay_stubs_employee_id",
            "pay_stubs",
            ["employee_id"],
            schema=SCHEMA,
        )


def downgrade() -> None:
    op.drop_table("pay_stubs", schema=SCHEMA)
    op.drop_table("payroll_runs", schema=SCHEMA)
    op.drop_table("employees", schema=SCHEMA)
    op.drop_table("departments", schema=SCHEMA)
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.payroll_run_status")
    op.execute(f"DROP TYPE IF EXISTS {SCHEMA}.employment_type")
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
