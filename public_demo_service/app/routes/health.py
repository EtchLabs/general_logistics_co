import time

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])

_start = time.monotonic()


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "ok",
        "uptime_seconds": round(time.monotonic() - _start, 2),
    }
