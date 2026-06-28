import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db.redis import close_redis
from app.middleware.correlation import CorrelationIdMiddleware
from app.routes import fulfillment, health

settings = get_settings()
logging.basicConfig(level=settings.log_level)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_redis()


app = FastAPI(
    title="GLC Fulfillment Service",
    version=settings.service_version,
    description="Warehouse fulfillment workflow management.",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
app.include_router(health.router)
app.include_router(fulfillment.router)
