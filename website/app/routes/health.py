import time
from typing import Any

from fastapi import APIRouter, Request

from app.config import get_settings

router = APIRouter(tags=["health"])

_start_time = time.monotonic()


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    settings = get_settings()
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "ok",
        "uptime_seconds": round(time.monotonic() - _start_time, 2),
        "correlation_id": getattr(request.state, "correlation_id", None),
    }
