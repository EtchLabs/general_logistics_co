import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db.mongo import close_mongo_client
from app.db.redis import close_redis
from app.middleware.correlation import CorrelationIdMiddleware
from app.routes import health, reports
from app.services.reporting_service import ensure_mongo_indexes

settings = get_settings()
logging.basicConfig(level=settings.log_level)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await ensure_mongo_indexes()
    yield
    await close_redis()
    await close_mongo_client()


app = FastAPI(
    title="GLC Reporting Service",
    version=settings.service_version,
    description="Aggregated business intelligence and operational reporting.",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
app.include_router(health.router)
app.include_router(reports.router)
