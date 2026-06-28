import logging

from fastapi import FastAPI

from app.config import get_settings
from app.middleware.correlation import CorrelationIdMiddleware
from app.routes import health, shipping

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="GLC Shipping Service",
    version=settings.service_version,
    description="Carrier integration for rate shopping, labels, and tracking.",
)

app.add_middleware(CorrelationIdMiddleware)
app.include_router(health.router)
app.include_router(shipping.router)
