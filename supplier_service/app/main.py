import logging

from fastapi import FastAPI

from app.config import get_settings
from app.middleware.correlation import CorrelationIdMiddleware
from app.routes import health, supplier_invoices, suppliers

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="GLC Supplier Service",
    version=settings.service_version,
    description="Supplier directory and purchase order management.",
)

app.add_middleware(CorrelationIdMiddleware)
app.include_router(health.router)
app.include_router(suppliers.router)
app.include_router(supplier_invoices.router)
