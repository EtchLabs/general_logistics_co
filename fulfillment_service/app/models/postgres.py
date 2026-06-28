import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import get_settings

SCHEMA = get_settings().postgres_schema


class Base(DeclarativeBase):
    pass


class FulfillmentJobStatus(str, enum.Enum):
    QUEUED = "queued"
    PICK = "pick"
    PACK = "pack"
    READY_TO_SHIP = "ready_to_ship"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class FulfillmentJob(Base):
    __tablename__ = "fulfillment_jobs"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    fulfillment_center_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    status: Mapped[FulfillmentJobStatus] = mapped_column(
        Enum(
            FulfillmentJobStatus,
            name="fulfillment_job_status",
            schema=SCHEMA,
            values_callable=lambda e: [m.value for m in e],
        ),
        default=FulfillmentJobStatus.QUEUED,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    pick_lists: Mapped[list["PickList"]] = relationship(back_populates="fulfillment_job")


class PickList(Base):
    __tablename__ = "pick_lists"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    fulfillment_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.fulfillment_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    line_items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    picker_id: Mapped[str | None] = mapped_column(String(50))
    picked_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    fulfillment_job: Mapped["FulfillmentJob"] = relationship(back_populates="pick_lists")
