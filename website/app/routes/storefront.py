from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.dependencies import cart_count, cart_subtotal, load_session, persist_session
from app.demo_data import DEMO_CHECKOUT
from app.services.api_client import gateway_client

router = APIRouter(tags=["storefront"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

WIDGET_ICONS = ["⚙️", "🔩", "🔧", "📦", "✨", "💎", "🏭", "🔲", "⬡", "🌿", "💡", "🛠️"]


def _cid(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None)


def _ctx(request: Request, session: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "request": request,
        "session": session,
        "cart_count": cart_count(session),
        "customer_name": session.get("customer_name"),
        **extra,
    }


async def _fetch_products(correlation_id: str | None) -> tuple[list[dict], str | None]:
    try:
        response = await gateway_client.get("/products", correlation_id=correlation_id)
        if response.status_code == 200:
            return response.json(), None
        return [], f"Catalog unavailable (HTTP {response.status_code})"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Product fetch failed: %s", exc)
        return [], "Unable to reach the product catalog."


async def _fetch_product_detail(product_id: str, correlation_id: str | None) -> dict | None:
    response = await gateway_client.get(f"/products/{product_id}", correlation_id=correlation_id)
    if response.status_code == 200:
        return response.json()
    return None


async def _price_for_sku(sku: str, quantity: int, correlation_id: str | None) -> dict | None:
    response = await gateway_client.get(
        f"/pricing/{sku}/calculate",
        params={"quantity": quantity},
        correlation_id=correlation_id,
    )
    if response.status_code == 200:
        return response.json()
    return None


def _find_cart_item(session: dict[str, Any], sku: str) -> dict | None:
    for item in session.get("cart", []):
        if item["sku"] == sku:
            return item
    return None


@router.get("/", response_class=HTMLResponse)
async def storefront_index(request: Request) -> HTMLResponse:
    session, _ = await load_session(request)
    products, error = await _fetch_products(_cid(request))
    enriched: list[dict] = []
    for idx, product in enumerate(products):
        detail = await _fetch_product_detail(product["id"], _cid(request))
        icon = WIDGET_ICONS[idx % len(WIDGET_ICONS)]
        price = None
        sku = None
        if detail and detail.get("variants"):
            sku = detail["variants"][0]["sku"]
            pricing = detail.get("pricing", {}).get(sku)
            if pricing:
                price = pricing.get("sale_price") or pricing.get("msrp")
        enriched.append({**product, "icon": icon, "display_price": price, "default_sku": sku})

    return templates.TemplateResponse(
        request,
        "storefront/index.html",
        _ctx(request, session, products=enriched, error=error, product_count=len(enriched)),
    )


@router.get("/products/{product_id}", response_class=HTMLResponse)
async def product_detail(request: Request, product_id: str) -> HTMLResponse:
    session, _ = await load_session(request)
    product = await _fetch_product_detail(product_id, _cid(request))
    if not product:
        return templates.TemplateResponse(
            request,
            "storefront/error.html",
            _ctx(request, session, message="Product not found."),
            status_code=404,
        )
    return templates.TemplateResponse(
        request,
        "storefront/product.html",
        _ctx(request, session, product=product),
    )


@router.post("/cart/add")
async def cart_add(
    request: Request,
    sku: str = Form(...),
    quantity: int = Form(1),
    product_name: str = Form(""),
) -> RedirectResponse:
    session, token = await load_session(request)
    quantity = max(1, min(quantity, 99))
    cid = _cid(request)

    price_data = await _price_for_sku(sku, quantity, cid)
    if not price_data:
        return RedirectResponse(url="/cart?error=pricing", status_code=303)

    unit_price = float(price_data["unit_price"])
    existing = _find_cart_item(session, sku)
    if existing:
        existing["quantity"] += quantity
        existing["unit_price"] = unit_price
        existing["line_total"] = existing["quantity"] * unit_price
    else:
        session.setdefault("cart", []).append(
            {
                "sku": sku,
                "product_name": product_name or sku,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": quantity * unit_price,
            }
        )

    response = RedirectResponse(url="/cart", status_code=303)
    await persist_session(response, session, token)
    return response


@router.get("/cart", response_class=HTMLResponse)
async def cart_view(request: Request, error: str | None = None) -> HTMLResponse:
    session, _ = await load_session(request)
    return templates.TemplateResponse(
        request,
        "storefront/cart.html",
        _ctx(
            request,
            session,
            cart_items=session.get("cart", []),
            subtotal=cart_subtotal(session),
            error=error,
        ),
    )


@router.post("/cart/update")
async def cart_update(
    request: Request,
    sku: str = Form(...),
    quantity: int = Form(...),
) -> RedirectResponse:
    session, token = await load_session(request)
    item = _find_cart_item(session, sku)
    if item:
        if quantity <= 0:
            session["cart"] = [i for i in session["cart"] if i["sku"] != sku]
        else:
            price_data = await _price_for_sku(sku, quantity, _cid(request))
            if price_data:
                item["quantity"] = quantity
                item["unit_price"] = float(price_data["unit_price"])
                item["line_total"] = quantity * item["unit_price"]
    response = RedirectResponse(url="/cart", status_code=303)
    await persist_session(response, session, token)
    return response


@router.post("/cart/remove")
async def cart_remove(request: Request, sku: str = Form(...)) -> RedirectResponse:
    session, token = await load_session(request)
    session["cart"] = [i for i in session["cart"] if i["sku"] != sku]
    response = RedirectResponse(url="/cart", status_code=303)
    await persist_session(response, session, token)
    return response


@router.get("/checkout", response_class=HTMLResponse)
async def checkout_view(request: Request) -> HTMLResponse:
    session, _ = await load_session(request)
    if not session.get("cart"):
        return RedirectResponse(url="/cart", status_code=303)
    return templates.TemplateResponse(
        request,
        "storefront/checkout.html",
        _ctx(request, session, cart_items=session["cart"], subtotal=cart_subtotal(session), demo=DEMO_CHECKOUT),
    )


@router.post("/checkout", response_model=None)
async def checkout_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(...),
    phone: str = Form(""),
    line1: str = Form(...),
    line2: str = Form(""),
    city: str = Form(...),
    state: str = Form(...),
    postal_code: str = Form(...),
    country: str = Form("US"),
    coupon_code: str = Form(""),
) -> Response:
    session, token = await load_session(request)
    cart = session.get("cart", [])
    if not cart:
        return RedirectResponse(url="/cart", status_code=303)

    cid = _cid(request)
    customer_id = session.get("customer_id")

    if not customer_id:
        reg = await gateway_client.post(
            "/customers/register",
            json={
                "email": email,
                "password": password,
                "first_name": first_name,
                "last_name": last_name,
                "phone": phone or None,
            },
            correlation_id=cid,
        )
        if reg.status_code == 409:
            login = await gateway_client.post(
                "/customers/login",
                json={"email": email, "password": password},
                correlation_id=cid,
            )
            if login.status_code != 200:
                return templates.TemplateResponse(
                    request,
                    "storefront/checkout.html",
                    _ctx(
                        request,
                        session,
                        cart_items=cart,
                        subtotal=cart_subtotal(session),
                        error="Account exists but login failed. Check your password.",
                        demo=DEMO_CHECKOUT,
                    ),
                    status_code=400,
                )
            customer = login.json()["customer"]
        elif reg.status_code != 201:
            detail = reg.json().get("detail", "Registration failed")
            return templates.TemplateResponse(
                request,
                "storefront/checkout.html",
                _ctx(
                    request,
                    session,
                    cart_items=cart,
                    subtotal=cart_subtotal(session),
                    error=str(detail),
                    demo=DEMO_CHECKOUT,
                ),
                status_code=400,
            )
        else:
            customer = reg.json()["customer"]

        customer_id = customer["id"]
        session["customer_id"] = customer_id
        session["customer_email"] = customer["email"]
        session["customer_name"] = f"{customer['first_name']} {customer['last_name']}"

        await gateway_client.post(
            f"/customers/{customer_id}/addresses",
            json={
                "label": "Shipping",
                "line1": line1,
                "line2": line2 or None,
                "city": city,
                "state": state.upper(),
                "postal_code": postal_code,
                "country": country.upper(),
                "is_default": True,
            },
            correlation_id=cid,
        )

    order_payload = {
        "customer_id": customer_id,
        "line_items": [{"sku": item["sku"], "quantity": item["quantity"]} for item in cart],
        "shipping_address": {
            "label": "Shipping",
            "line1": line1,
            "line2": line2 or None,
            "city": city,
            "state": state.upper(),
            "postal_code": postal_code,
            "country": country.upper(),
        },
        "coupon_code": coupon_code.strip() or None,
        "shipping_total": "0.00",
    }

    order_resp = await gateway_client.post("/orders", json=order_payload, correlation_id=cid)
    if order_resp.status_code != 201:
        detail = order_resp.json().get("detail", order_resp.text)
        logger.error("Order creation failed: %s", detail)
        return templates.TemplateResponse(
            request,
            "storefront/checkout.html",
            _ctx(
                request,
                session,
                cart_items=cart,
                subtotal=cart_subtotal(session),
                error=f"Could not place order: {detail}",
                demo=DEMO_CHECKOUT,
            ),
            status_code=400,
        )

    order = order_resp.json()
    session["cart"] = []
    session["last_order_id"] = order["id"]
    response = RedirectResponse(url=f"/order/confirmation/{order['id']}", status_code=303)
    await persist_session(response, session, token)
    return response


@router.get("/order/confirmation/{order_id}", response_class=HTMLResponse)
async def order_confirmation(request: Request, order_id: str) -> HTMLResponse:
    session, _ = await load_session(request)
    order = None
    resp = await gateway_client.get(f"/orders/{order_id}", correlation_id=_cid(request))
    if resp.status_code == 200:
        order = resp.json()
    return templates.TemplateResponse(
        request,
        "storefront/confirmation.html",
        _ctx(request, session, order=order, order_id=order_id),
    )
