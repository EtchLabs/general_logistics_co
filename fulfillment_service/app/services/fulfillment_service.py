import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.redis import get_redis
from app.models.postgres import FulfillmentJob, FulfillmentJobStatus, PickList
from app.models.schemas import FulfillmentJobCreate


VALID_TRANSITIONS: dict[FulfillmentJobStatus, set[FulfillmentJobStatus]] = {
    FulfillmentJobStatus.QUEUED: {FulfillmentJobStatus.PICK, FulfillmentJobStatus.CANCELLED},
    FulfillmentJobStatus.PICK: {FulfillmentJobStatus.PACK, FulfillmentJobStatus.CANCELLED},
    FulfillmentJobStatus.PACK: {
        FulfillmentJobStatus.READY_TO_SHIP,
        FulfillmentJobStatus.CANCELLED,
    },
    FulfillmentJobStatus.READY_TO_SHIP: {FulfillmentJobStatus.COMPLETED},
    FulfillmentJobStatus.COMPLETED: set(),
    FulfillmentJobStatus.CANCELLED: set(),
}


async def enqueue_job(job_id: UUID) -> None:
    settings = get_settings()
    await get_redis().lpush(settings.job_queue_key, str(job_id))


async def get_job_or_404(session: AsyncSession, job_id: UUID) -> FulfillmentJob:
    result = await session.execute(
        select(FulfillmentJob)
        .options(selectinload(FulfillmentJob.pick_lists))
        .where(FulfillmentJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Fulfillment job not found")
    return job


async def create_fulfillment_job(
    session: AsyncSession, payload: FulfillmentJobCreate
) -> FulfillmentJob:
    line_items = [item.model_dump() for item in payload.line_items]
    job = FulfillmentJob(
        order_id=payload.order_id,
        fulfillment_center_id=payload.fulfillment_center_id,
        status=FulfillmentJobStatus.QUEUED,
    )
    session.add(job)
    await session.flush()

    pick_list = PickList(
        fulfillment_job_id=job.id,
        line_items=line_items,
        picked_quantity=0,
    )
    session.add(pick_list)
    await session.commit()
    await session.refresh(job)

    await enqueue_job(job.id)
    await get_redis().publish(
        "fulfillment.job.created",
        json.dumps({"job_id": str(job.id), "order_id": str(job.order_id)}, default=str),
    )
    return await get_job_or_404(session, job.id)


async def update_job_status(
    session: AsyncSession, job_id: UUID, new_status: FulfillmentJobStatus
) -> FulfillmentJob:
    job = await get_job_or_404(session, job_id)
    allowed = VALID_TRANSITIONS.get(job.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from {job.status.value} to {new_status.value}",
        )
    job.status = new_status
    await session.commit()
    await session.refresh(job)
    await get_redis().publish(
        "fulfillment.job.status_changed",
        json.dumps(
            {"job_id": str(job.id), "order_id": str(job.order_id), "status": new_status.value},
            default=str,
        ),
    )
    return await get_job_or_404(session, job.id)
