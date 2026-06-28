import logging
from typing import Any

import httpx
from fastapi import APIRouter, Request, Response
from redis.asyncio import Redis

from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["proxy"])

# Longest-prefix-first routing to downstream services.
ROUTE_MAP: list[tuple[str, str]] = [
    ("/reports/sales-summary", "reporting_service"),
    ("/reports/inventory-summary", "reporting_service"),
    ("/reports/income-statement", "accounting_service"),
    ("/customers", "customer_service"),
    ("/orders", "order_service"),
    ("/categories", "product_service"),
    ("/products", "product_service"),
    ("/pricing", "product_service"),
    ("/promotions", "product_service"),
    ("/coupons", "product_service"),
    ("/fulfillment-centers", "inventory_service"),
    ("/inventory", "inventory_service"),
    ("/fulfillment", "fulfillment_service"),
    ("/shipping", "shipping_service"),
    ("/payments", "payment_service"),
    ("/tax", "tax_service"),
    ("/suppliers", "supplier_service"),
    ("/purchase-orders", "supplier_service"),
    ("/supplier-invoices", "supplier_service"),
    ("/accounts", "accounting_service"),
    ("/journal-entries", "accounting_service"),
    ("/employees", "hr_payroll_service"),
    ("/departments", "hr_payroll_service"),
    ("/payroll", "hr_payroll_service"),
    ("/notifications", "notification_service"),
]


def resolve_service(path: str) -> str | None:
    settings = get_settings()
    for prefix, service_key in ROUTE_MAP:
        if path == prefix or path.startswith(f"{prefix}/"):
            return getattr(settings, f"{service_key}_url")
    return None


async def _rate_limit(client_ip: str) -> None:
    settings = get_settings()
    redis: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        key = f"gateway:rate:{client_ip}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, settings.rate_limit_window_seconds)
        if count > settings.rate_limit_requests:
            from fastapi import HTTPException

            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    finally:
        await redis.aclose()


@router.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def proxy_request(full_path: str, request: Request) -> Response:
    path = f"/{full_path}" if full_path else "/"
    if path in {"/health", "/"}:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Use dedicated health routes")

    target_base = resolve_service(path)
    if target_base is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"No route for {path}")

    client_ip = request.client.host if request.client else "unknown"
    await _rate_limit(client_ip)

    target_url = f"{target_base.rstrip('/')}{path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in {"host", "content-length", "connection"}
    }
    correlation_id = getattr(request.state, "correlation_id", None)
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id

    body = await request.body()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            upstream = await client.request(
                request.method,
                target_url,
                headers=headers,
                content=body,
            )
    except httpx.RequestError as exc:
        logger.error("Upstream error for %s: %s", path, exc)
        from fastapi import HTTPException

        raise HTTPException(status_code=502, detail="Upstream service unavailable") from exc

    response_headers = {
        k: v
        for k, v in upstream.headers.items()
        if k.lower() not in {"content-encoding", "transfer-encoding", "connection"}
    }
    if correlation_id:
        response_headers["X-Correlation-ID"] = correlation_id

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=upstream.headers.get("content-type"),
    )
