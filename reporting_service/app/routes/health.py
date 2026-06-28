import time
from typing import Any

from fastapi import APIRouter, Request
from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis

from app.config import get_settings
from app.db.redis import get_redis

router = APIRouter(tags=["health"])

_start_time = time.monotonic()


async def _check_mongo() -> dict[str, Any]:
    settings = get_settings()
    client: AsyncIOMotorClient | None = None
    try:
        client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=3000)
        await client.admin.command("ping")
        return {"status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}
    finally:
        if client is not None:
            client.close()


async def _check_redis() -> dict[str, Any]:
    try:
        client: Redis = get_redis()
        if await client.ping():
            return {"status": "ok"}
        return {"status": "error", "detail": "unexpected ping response"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": str(exc)}


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    settings = get_settings()
    dependencies = {
        "mongo": await _check_mongo(),
        "redis": await _check_redis(),
    }
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
        "message": "General Logistics Co Reporting Service",
    }
