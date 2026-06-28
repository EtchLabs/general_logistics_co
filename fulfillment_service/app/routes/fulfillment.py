from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_session
from app.models.schemas import (
    FulfillmentJobCreate,
    FulfillmentJobOut,
    FulfillmentJobStatusUpdate,
    PickListOut,
)
from app.services.fulfillment_service import create_fulfillment_job, get_job_or_404, update_job_status

router = APIRouter(prefix="/fulfillment", tags=["fulfillment"])


@router.post("/jobs", response_model=FulfillmentJobOut, status_code=201)
async def create_job(
    payload: FulfillmentJobCreate,
    session: AsyncSession = Depends(get_session),
) -> FulfillmentJobOut:
    job = await create_fulfillment_job(session, payload)
    return FulfillmentJobOut(
        id=job.id,
        order_id=job.order_id,
        fulfillment_center_id=job.fulfillment_center_id,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        pick_lists=[PickListOut.model_validate(pl) for pl in job.pick_lists],
    )


@router.get("/jobs/{job_id}", response_model=FulfillmentJobOut)
async def get_job(
    job_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> FulfillmentJobOut:
    job = await get_job_or_404(session, job_id)
    return FulfillmentJobOut(
        id=job.id,
        order_id=job.order_id,
        fulfillment_center_id=job.fulfillment_center_id,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        pick_lists=[PickListOut.model_validate(pl) for pl in job.pick_lists],
    )


@router.patch("/jobs/{job_id}/status", response_model=FulfillmentJobOut)
async def patch_job_status(
    job_id: UUID,
    payload: FulfillmentJobStatusUpdate,
    session: AsyncSession = Depends(get_session),
) -> FulfillmentJobOut:
    job = await update_job_status(session, job_id, payload.status)
    return FulfillmentJobOut(
        id=job.id,
        order_id=job.order_id,
        fulfillment_center_id=job.fulfillment_center_id,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        pick_lists=[PickListOut.model_validate(pl) for pl in job.pick_lists],
    )
