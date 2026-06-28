from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.postgres import Employee, PayStub, PayrollRun, PayrollRunStatus
from app.models.schemas import PayrollRunCreate


def _biweekly_gross(employee: Employee) -> Decimal:
    if employee.salary is not None:
        return (employee.salary / Decimal("26")).quantize(Decimal("0.01"))
    if employee.hourly_rate is not None:
        return (employee.hourly_rate * Decimal("80")).quantize(Decimal("0.01"))
    return Decimal("0")


def _calculate_deductions(gross: Decimal) -> Decimal:
    settings = get_settings()
    federal = gross * Decimal(str(settings.federal_tax_rate_percent / 100))
    fica = gross * Decimal(str(settings.fica_rate_percent / 100))
    return (federal + fica).quantize(Decimal("0.01"))


async def get_payroll_run_or_404(session: AsyncSession, run_id: UUID) -> PayrollRun:
    result = await session.execute(
        select(PayrollRun)
        .options(selectinload(PayrollRun.pay_stubs))
        .where(PayrollRun.id == run_id)
    )
    payroll_run = result.scalar_one_or_none()
    if payroll_run is None:
        raise HTTPException(status_code=404, detail="Payroll run not found")
    return payroll_run


async def run_payroll(session: AsyncSession, payload: PayrollRunCreate) -> PayrollRun:
    if payload.period_end < payload.period_start:
        raise HTTPException(status_code=400, detail="period_end must be on or after period_start")

    result = await session.execute(select(Employee).where(Employee.is_active.is_(True)))
    employees = list(result.scalars().all())
    if not employees:
        raise HTTPException(status_code=400, detail="No active employees to pay")

    payroll_run = PayrollRun(
        period_start=payload.period_start,
        period_end=payload.period_end,
        status=PayrollRunStatus.PROCESSING,
    )
    session.add(payroll_run)
    await session.flush()

    total_gross = Decimal("0")
    total_net = Decimal("0")

    for employee in employees:
        gross = _biweekly_gross(employee)
        deductions = _calculate_deductions(gross)
        net = gross - deductions
        stub = PayStub(
            payroll_run_id=payroll_run.id,
            employee_id=employee.id,
            gross_pay=gross,
            deductions=deductions,
            net_pay=net,
        )
        session.add(stub)
        total_gross += gross
        total_net += net

    payroll_run.total_gross = total_gross
    payroll_run.total_net = total_net
    payroll_run.status = PayrollRunStatus.COMPLETED

    await session.commit()
    return await get_payroll_run_or_404(session, payroll_run.id)
