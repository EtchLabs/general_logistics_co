from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_session
from app.models.postgres import Employee
from app.models.schemas import EmployeeCreate, EmployeeOut

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("", response_model=list[EmployeeOut])
async def list_employees(session: AsyncSession = Depends(get_session)) -> list[Employee]:
    result = await session.execute(select(Employee).order_by(Employee.last_name, Employee.first_name))
    return list(result.scalars().all())


@router.post("", response_model=EmployeeOut, status_code=201)
async def create_employee(
    payload: EmployeeCreate,
    session: AsyncSession = Depends(get_session),
) -> Employee:
    existing = await session.execute(select(Employee).where(Employee.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Employee email already exists")

    employee = Employee(
        department_id=payload.department_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email.lower(),
        hire_date=payload.hire_date,
        employment_type=payload.employment_type,
        salary=payload.salary,
        hourly_rate=payload.hourly_rate,
    )
    session.add(employee)
    await session.commit()
    await session.refresh(employee)
    return employee
