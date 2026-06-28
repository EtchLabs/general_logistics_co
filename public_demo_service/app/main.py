import asyncio
import logging

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.events import event_hub
from app.routes import demo, health

load_dotenv()

settings = get_settings()
logging.basicConfig(level=settings.log_level)

app = FastAPI(
    title="GLC Public Demo",
    version=settings.service_version,
    description="Live visual demo of General Logistics Co operations.",
)

app.include_router(health.router)
app.include_router(demo.router)

try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except RuntimeError:
    pass

_stop_event = asyncio.Event()


@app.on_event("startup")
async def startup() -> None:
    asyncio.create_task(event_hub.redis_listener(_stop_event))
    asyncio.create_task(event_hub.poll_orders_loop(_stop_event))
    asyncio.create_task(event_hub.poll_extras_loop(_stop_event))
    logging.getLogger(__name__).info("Public demo service started on port 8021")


@app.on_event("shutdown")
async def shutdown() -> None:
    _stop_event.set()
