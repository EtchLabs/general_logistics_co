import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db.mongo import close_mongo_client
from app.db.redis import close_redis
from app.middleware.correlation import CorrelationIdMiddleware
from app.routes import health, notifications
from app.services.notification_service import ensure_mongo_indexes, redis_subscriber_loop

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await ensure_mongo_indexes()
    stop_event = asyncio.Event()
    subscriber_task = asyncio.create_task(redis_subscriber_loop(stop_event))
    logger.info("Notification service started; Redis subscriber running")
    yield
    stop_event.set()
    subscriber_task.cancel()
    try:
        await subscriber_task
    except asyncio.CancelledError:
        pass
    await close_redis()
    await close_mongo_client()


app = FastAPI(
    title="GLC Notification Service",
    version=settings.service_version,
    description="Centralized outbound communication hub.",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
app.include_router(health.router)
app.include_router(notifications.router)
