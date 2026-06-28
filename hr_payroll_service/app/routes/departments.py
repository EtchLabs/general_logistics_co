from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_session
from app.models.postgres import Department
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class DepartmentCreate(BaseModel):
    code: str
    name: str


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    created_at: datetime


router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("", response_model=list[DepartmentOut])
async def list_departments(session: AsyncSession = Depends(get_session)) -> list[Department]:
    result = await session.execute(select(Department).order_by(Department.code))
    return list(result.scalars().all())


@router.post("", response_model=DepartmentOut, status_code=201)
async def create_department(
    payload: DepartmentCreate,
    session: AsyncSession = Depends(get_session),
) -> Department:
    existing = await session.execute(select(Department).where(Department.code == payload.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Department code already exists")
    dept = Department(code=payload.code.upper(), name=payload.name)
    session.add(dept)
    await session.commit()
    await session.refresh(dept)
    return dept
