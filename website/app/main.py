import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.middleware.correlation import CorrelationIdMiddleware
from app.routes import admin, health, storefront

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="GLC Website",
    version=settings.service_version,
    description="Customer storefront and internal admin dashboard.",
)

app.add_middleware(CorrelationIdMiddleware)
app.include_router(health.router)
app.include_router(storefront.router)
app.include_router(admin.router)

try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except RuntimeError:
    pass
