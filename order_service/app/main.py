import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db.redis import close_redis
from app.middleware.correlation import CorrelationIdMiddleware
from app.routes import health, orders

settings = get_settings()
logging.basicConfig(level=settings.log_level)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_redis()


app = FastAPI(
    title="GLC Order Service",
    version=settings.service_version,
    description="Order lifecycle management from placement through completion.",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
app.include_router(health.router)
app.include_router(orders.router)
