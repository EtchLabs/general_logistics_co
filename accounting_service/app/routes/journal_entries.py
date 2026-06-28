from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_session
from app.models.schemas import JournalEntryCreate, JournalEntryOut
from app.services.accounting_service import create_journal_entry

router = APIRouter(prefix="/journal-entries", tags=["journal-entries"])


@router.post("", response_model=JournalEntryOut, status_code=201)
async def post_journal_entry(
    payload: JournalEntryCreate,
    session: AsyncSession = Depends(get_session),
):
    return await create_journal_entry(session, payload)
