"""Customer simulator entrypoint with asyncio loop and health endpoint."""

from __future__ import annotations

import asyncio
import logging
import threading
import time

import uvicorn
from fastapi import FastAPI

from config import get_settings
from seed import seed_catalog
from simulator import CustomerSimulator

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

simulator = CustomerSimulator()
stop_event = asyncio.Event()
_start_time = time.monotonic()

health_app = FastAPI(title="Customer Simulator Health")


@health_app.get("/health")
async def health() -> dict:
    return {
        "service": "customer_simulator",
        "status": "ok",
        "uptime_seconds": round(time.monotonic() - _start_time, 2),
        "stats": simulator.stats(),
    }


def run_health_server() -> None:
    uvicorn.run(health_app, host="0.0.0.0", port=settings.simulator_health_port, log_level="warning")


async def main_async() -> None:
    logger.info(
        "Starting customer simulator — order every %.0f-%.0fs (~%.0f/hr, varied carts)",
        settings.simulator_order_interval_min_seconds,
        settings.simulator_order_interval_max_seconds,
        settings.estimated_orders_per_hour(),
    )
    try:
        await seed_catalog(settings.api_gateway_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Catalog seed skipped or failed: %s", exc)

    await simulator.run_loop(stop_event)


def main() -> None:
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Shutting down customer simulator")
        stop_event.set()


if __name__ == "__main__":
    main()
