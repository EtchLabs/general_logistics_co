import time
from typing import Any

import asyncpg
from fastapi import APIRouter, Request

from app.config import get_settings

router = APIRouter(tags=["health"])

_start_time = time.monotonic()


async def _check_postgres() -> dict[str, Any]:
    settings = get_settings()
    try:
        conn = await asyncpg.connect(settings.postgres_dsn, timeout=3)
        try:
            await conn.fetchval("SELECT 1")
            return {"status": "ok"}
        finally:
            await conn.close()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    settings = get_settings()
    dependencies = {"postgres": await _check_postgres()}
    overall = (
        "ok"
        if all(dep["status"] == "ok" for dep in dependencies.values())
        else "degraded"
    )
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": overall,
        "uptime_seconds": round(time.monotonic() - _start_time, 2),
        "correlation_id": getattr(request.state, "correlation_id", None),
        "dependencies": dependencies,
    }


@router.get("/")
async def root() -> dict[str, str]:
    settings = get_settings()
    return {
        "service": settings.service_name,
        "message": "General Logistics Co HR & Payroll Service",
    }
