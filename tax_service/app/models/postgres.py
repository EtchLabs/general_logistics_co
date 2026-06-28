import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import get_settings

SCHEMA = get_settings().postgres_schema


class Base(DeclarativeBase):
    pass


class LedgerStatus(str, enum.Enum):
    COLLECTED = "collected"
    REMITTED = "remitted"


class TaxRate(Base):
    __tablename__ = "tax_rates"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    jurisdiction: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    product_category: Mapped[str] = mapped_column(String(50), default="general", nullable=False)
    rate_percent: Mapped[Decimal] = mapped_column(Numeric(6, 4), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TaxCollectedLedger(Base):
    __tablename__ = "tax_collected_ledger"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    jurisdiction: Mapped[str] = mapped_column(String(100), nullable=False)
    tax_rate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.tax_rates.id"),
        nullable=False,
    )
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[LedgerStatus] = mapped_column(
        Enum(
            LedgerStatus,
            name="ledger_status",
            schema=SCHEMA,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=LedgerStatus.COLLECTED,
        nullable=False,
        index=True,
    )
    remittance_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
