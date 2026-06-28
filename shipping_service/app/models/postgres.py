import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import get_settings

SCHEMA = get_settings().postgres_schema


class Base(DeclarativeBase):
    pass


class ShipmentStatus(str, enum.Enum):
    LABEL_CREATED = "label_created"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    EXCEPTION = "exception"


class Shipment(Base):
    __tablename__ = "shipments"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    fulfillment_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    carrier: Mapped[str] = mapped_column(String(50), nullable=False)
    service_level: Mapped[str] = mapped_column(String(50), nullable=False)
    tracking_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    label_url: Mapped[str] = mapped_column(String(500), nullable=False)
    weight_oz: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    shipping_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[ShipmentStatus] = mapped_column(
        Enum(
            ShipmentStatus,
            name="shipment_status",
            schema=SCHEMA,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ShipmentStatus.LABEL_CREATED,
        nullable=False,
        index=True,
    )
    ship_to_address: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tracking_events: Mapped[list["TrackingEvent"]] = relationship(back_populates="shipment")


class TrackingEvent(Base):
    __tablename__ = "tracking_events"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    location: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    shipment: Mapped["Shipment"] = relationship(back_populates="tracking_events")
