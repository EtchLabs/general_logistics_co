import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.api_client import gateway_client

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request) -> HTMLResponse:
    orders: list[dict] = []
    products: list[dict] = []
    errors: list[str] = []
    correlation_id = getattr(request.state, "correlation_id", None)

    order_stats: dict = {}
    try:
        stats_response = await gateway_client.get("/orders/stats", correlation_id=correlation_id)
        if stats_response.status_code == 200:
            order_stats = stats_response.json()
        else:
            errors.append(f"Order stats unavailable (HTTP {stats_response.status_code})")
    except Exception as exc:  # noqa: BLE001
        errors.append("Unable to load order stats.")
        logger.exception("Order stats fetch failed: %s", exc)

    try:
        orders_response = await gateway_client.get("/orders", correlation_id=correlation_id)
        if orders_response.status_code == 200:
            orders = orders_response.json()
        else:
            errors.append(f"Orders unavailable (HTTP {orders_response.status_code})")
    except Exception as exc:  # noqa: BLE001
        errors.append("Unable to load orders.")
        logger.exception("Order fetch failed: %s", exc)

    try:
        products_response = await gateway_client.get("/products", correlation_id=correlation_id)
        if products_response.status_code == 200:
            products = products_response.json()
        else:
            errors.append(f"Products unavailable (HTTP {products_response.status_code})")
    except Exception as exc:  # noqa: BLE001
        errors.append("Unable to load products.")
        logger.exception("Product fetch failed: %s", exc)

    by_status = order_stats.get("by_status", {})
    pending_orders = by_status.get("pending", 0) + by_status.get("confirmed", 0)
    in_fulfillment = by_status.get("in_fulfillment", 0)

    return templates.TemplateResponse(
        request,
        "admin/index.html",
        {
            "orders": orders[:20],
            "products": products[:12],
            "stats": {
                "total_orders": order_stats.get("total", len(orders)),
                "pending_orders": pending_orders,
                "in_fulfillment": in_fulfillment,
                "catalog_size": len(products),
            },
            "errors": errors,
        },
    )
