"""Supplier simulator entrypoint."""

from __future__ import annotations

import asyncio
import logging

from config import get_settings
from simulator import SupplierSimulator

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main_async() -> None:
    simulator = SupplierSimulator()
    stop_event = asyncio.Event()
    logger.info("Starting supplier simulator (poll every %ds)", settings.supplier_poll_interval_seconds)
    await simulator.run_loop(stop_event)


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Shutting down supplier simulator")


if __name__ == "__main__":
    main()
