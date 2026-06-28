import logging

from fastapi import FastAPI

from app.config import get_settings
from app.middleware.correlation import CorrelationIdMiddleware
from app.routes import health, payments

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="GLC Payment Service",
    version=settings.service_version,
    description="Payment authorization, capture, and refund processing.",
)

app.add_middleware(CorrelationIdMiddleware)
app.include_router(health.router)
app.include_router(payments.router)
