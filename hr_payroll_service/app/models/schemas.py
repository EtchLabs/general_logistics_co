from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.postgres import EmploymentType, PayrollRunStatus


class EmployeeCreate(BaseModel):
    department_id: UUID | None = None
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    hire_date: date
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    salary: Decimal | None = Field(default=None, ge=0)
    hourly_rate: Decimal | None = Field(default=None, ge=0)


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    department_id: UUID | None
    first_name: str
    last_name: str
    email: EmailStr
    hire_date: date
    employment_type: EmploymentType
    salary: Decimal | None
    hourly_rate: Decimal | None
    is_active: bool
    created_at: datetime


class PayrollRunCreate(BaseModel):
    period_start: date
    period_end: date


class PayStubOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    payroll_run_id: UUID
    employee_id: UUID
    gross_pay: Decimal
    deductions: Decimal
    net_pay: Decimal


class PayrollRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    period_start: date
    period_end: date
    status: PayrollRunStatus
    total_gross: Decimal
    total_net: Decimal
    created_at: datetime
    pay_stubs: list[PayStubOut] = []
