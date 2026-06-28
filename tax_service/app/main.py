import logging

from fastapi import FastAPI

from app.config import get_settings
from app.middleware.correlation import CorrelationIdMiddleware
from app.routes import health, tax

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="GLC Tax Service",
    version=settings.service_version,
    description="Sales tax calculation, collection tracking, and remittance.",
)

app.add_middleware(CorrelationIdMiddleware)
app.include_router(health.router)
app.include_router(tax.router)
