from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_session
from app.models.schemas import IncomeStatementOut
from app.services.accounting_service import get_income_statement

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/income-statement", response_model=IncomeStatementOut)
async def income_statement(session: AsyncSession = Depends(get_session)) -> dict:
    return await get_income_statement(session)
