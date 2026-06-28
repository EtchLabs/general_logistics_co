import logging

from fastapi import FastAPI

from app.config import get_settings
from app.middleware.correlation import CorrelationIdMiddleware
from app.routes import departments, employees, health, payroll

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="GLC HR & Payroll Service",
    version=settings.service_version,
    description="Human resources and payroll processing.",
)

app.add_middleware(CorrelationIdMiddleware)
app.include_router(health.router)
app.include_router(departments.router)
app.include_router(employees.router)
app.include_router(payroll.router)
