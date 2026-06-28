import logging

from fastapi import FastAPI

from app.config import get_settings
from app.middleware.correlation import CorrelationIdMiddleware
from app.routes import health, proxy

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="GLC API Gateway",
    version=settings.service_version,
    description="Single ingress point for General Logistics Co microservices.",
)

app.add_middleware(CorrelationIdMiddleware)
app.include_router(health.router)
app.include_router(proxy.router)
