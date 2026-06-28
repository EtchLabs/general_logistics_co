import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db.mongo import close_mongo_client
from app.middleware.correlation import CorrelationIdMiddleware
from app.routes import customers, health
from app.services.customer_service import ensure_mongo_indexes

settings = get_settings()
logging.basicConfig(level=settings.log_level)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await ensure_mongo_indexes()
    yield
    await close_mongo_client()


app = FastAPI(
    title="GLC Customer Service",
    version=settings.service_version,
    description="Customer identity, profile, and relationship management.",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
app.include_router(health.router)
app.include_router(customers.router)
