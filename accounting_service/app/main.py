import logging

from fastapi import FastAPI

from app.config import get_settings
from app.middleware.correlation import CorrelationIdMiddleware
from app.routes import accounts, health, journal_entries, reports

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="GLC Accounting Service",
    version=settings.service_version,
    description="Double-entry bookkeeping and financial reporting.",
)

app.add_middleware(CorrelationIdMiddleware)
app.include_router(health.router)
app.include_router(accounts.router)
app.include_router(journal_entries.router)
app.include_router(reports.router)
