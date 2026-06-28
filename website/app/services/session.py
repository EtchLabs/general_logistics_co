import json
import secrets
from typing import Any

from app.config import get_settings

_memory_sessions: dict[str, dict[str, Any]] = {}


class SessionStore:
    """Optional Redis-backed session store with in-memory fallback stub."""

    def __init__(self) -> None:
        settings = get_settings()
        self._ttl = settings.session_ttl_seconds
        self._redis = None
        if settings.use_redis_sessions:
            try:
                from redis.asyncio import Redis

                self._redis = Redis.from_url(settings.redis_url, decode_responses=True)
            except Exception:  # noqa: BLE001
                self._redis = None

    async def create(self, data: dict[str, Any]) -> str:
        token = secrets.token_urlsafe(32)
        await self.set(token, data)
        return token

    async def get(self, token: str) -> dict[str, Any] | None:
        if self._redis is not None:
            raw = await self._redis.get(f"session:{token}")
            if raw:
                return json.loads(raw)
            return None
        return _memory_sessions.get(token)

    async def set(self, token: str, data: dict[str, Any]) -> None:
        if self._redis is not None:
            await self._redis.setex(f"session:{token}", self._ttl, json.dumps(data, default=str))
            return
        _memory_sessions[token] = data

    async def delete(self, token: str) -> None:
        if self._redis is not None:
            await self._redis.delete(f"session:{token}")
            return
        _memory_sessions.pop(token, None)


session_store = SessionStore()
