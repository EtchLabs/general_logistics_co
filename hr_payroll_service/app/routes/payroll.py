from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_session
from app.models.schemas import PayrollRunCreate, PayrollRunOut
from app.services.payroll_service import get_payroll_run_or_404, run_payroll

router = APIRouter(prefix="/payroll", tags=["payroll"])


@router.post("/run", response_model=PayrollRunOut, status_code=201)
async def create_payroll_run(
    payload: PayrollRunCreate,
    session: AsyncSession = Depends(get_session),
):
    return await run_payroll(session, payload)


@router.get("/runs/{run_id}", response_model=PayrollRunOut)
async def get_payroll_run(
    run_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    return await get_payroll_run_or_404(session, run_id)
