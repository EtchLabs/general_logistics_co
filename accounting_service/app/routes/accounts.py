from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_session
from app.models.postgres import Account
from app.models.schemas import AccountCreate, AccountOut

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
async def list_accounts(session: AsyncSession = Depends(get_session)) -> list[Account]:
    result = await session.execute(select(Account).order_by(Account.code))
    return list(result.scalars().all())


@router.post("", response_model=AccountOut, status_code=201)
async def create_account(
    payload: AccountCreate,
    session: AsyncSession = Depends(get_session),
) -> Account:
    existing = await session.execute(select(Account).where(Account.code == payload.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Account code already exists")

    account = Account(
        code=payload.code,
        name=payload.name,
        account_type=payload.account_type,
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account
