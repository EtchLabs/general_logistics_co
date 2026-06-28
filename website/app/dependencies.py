from __future__ import annotations

from typing import Any

from fastapi import Request, Response

from app.config import get_settings
from app.services.session import session_store


def empty_session() -> dict[str, Any]:
    return {"cart": [], "customer_id": None, "customer_email": None, "customer_name": None}


async def load_session(request: Request) -> tuple[dict[str, Any], str | None]:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return empty_session(), None
    data = await session_store.get(token)
    if not data:
        return empty_session(), token
    data.setdefault("cart", [])
    return data, token


async def persist_session(response: Response, data: dict[str, Any], token: str | None) -> str:
    settings = get_settings()
    if token:
        await session_store.set(token, data)
        session_token = token
    else:
        session_token = await session_store.create(data)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_token,
        httponly=True,
        max_age=settings.session_ttl_seconds,
        samesite="lax",
    )
    return session_token


def cart_count(session: dict[str, Any]) -> int:
    return sum(item.get("quantity", 0) for item in session.get("cart", []))


def cart_subtotal(session: dict[str, Any]) -> float:
    total = 0.0
    for item in session.get("cart", []):
        total += float(item.get("unit_price", 0)) * int(item.get("quantity", 0))
    return total
