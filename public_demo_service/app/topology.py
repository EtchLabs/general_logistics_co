"""Board topology: node positions and flow paths for the public demo."""

from __future__ import annotations

# Miro-style node layout (viewBox 0 0 1100 620)
BUSINESS_NODES: dict[str, dict] = {
    "storefront": {
        "label": "Online Storefront",
        "subtitle": "Customers browse & buy widgets",
        "x": 60,
        "y": 80,
        "w": 170,
        "h": 72,
        "color": "#ffffff",
    },
    "orders": {
        "label": "Order Management",
        "subtitle": "Quotes, orders & returns",
        "x": 300,
        "y": 80,
        "w": 170,
        "h": 72,
        "color": "#ffffff",
    },
    "inventory": {
        "label": "Warehouse & Stock",
        "subtitle": "Inventory across fulfillment centers",
        "x": 540,
        "y": 80,
        "w": 170,
        "h": 72,
        "color": "#ffffff",
    },
    "fulfillment": {
        "label": "Fulfillment Operations",
        "subtitle": "Pick, pack & ship prep",
        "x": 780,
        "y": 80,
        "w": 170,
        "h": 72,
        "color": "#ffffff",
    },
    "shipping": {
        "label": "Shipping & Delivery",
        "subtitle": "Carriers, labels & tracking",
        "x": 780,
        "y": 220,
        "w": 170,
        "h": 72,
        "color": "#ffffff",
    },
    "payments": {
        "label": "Billing & Payments",
        "subtitle": "Authorize, capture & refunds",
        "x": 300,
        "y": 220,
        "w": 170,
        "h": 72,
        "color": "#ffffff",
    },
    "finance": {
        "label": "Finance & Accounting",
        "subtitle": "Ledger, tax & reporting",
        "x": 540,
        "y": 220,
        "w": 170,
        "h": 72,
        "color": "#ffffff",
    },
    "suppliers": {
        "label": "Supplier Network",
        "subtitle": "Purchase orders & inbound stock",
        "x": 540,
        "y": 380,
        "w": 170,
        "h": 72,
        "color": "#ffffff",
    },
    "people": {
        "label": "Workforce & Payroll",
        "subtitle": "Employees & biweekly payroll",
        "x": 300,
        "y": 380,
        "w": 170,
        "h": 72,
        "color": "#ffffff",
    },
    "customer_comms": {
        "label": "Customer Updates",
        "subtitle": "Email & order notifications",
        "x": 780,
        "y": 380,
        "w": 170,
        "h": 72,
        "color": "#ffffff",
    },
}

MICROSERVICE_NODES: dict[str, dict] = {
    "website":      {"label": "Website",      "x": 40,  "y": 40,  "w": 120, "h": 56, "color": "#ffffff"},
    "gateway":      {"label": "API Gateway",  "x": 220, "y": 40,  "w": 120, "h": 56, "color": "#ffffff"},
    "customer":     {"label": "Customer",     "x": 40,  "y": 140, "w": 120, "h": 56, "color": "#ffffff"},
    "product":      {"label": "Product",      "x": 180, "y": 140, "w": 120, "h": 56, "color": "#ffffff"},
    "order":        {"label": "Order",        "x": 320, "y": 140, "w": 120, "h": 56, "color": "#ffffff"},
    "inventory":    {"label": "Inventory",    "x": 460, "y": 140, "w": 120, "h": 56, "color": "#ffffff"},
    "fulfillment":  {"label": "Fulfillment",  "x": 600, "y": 140, "w": 120, "h": 56, "color": "#ffffff"},
    "shipping":     {"label": "Shipping",     "x": 740, "y": 140, "w": 120, "h": 56, "color": "#ffffff"},
    "payment":      {"label": "Payment",      "x": 180, "y": 260, "w": 120, "h": 56, "color": "#ffffff"},
    "tax":          {"label": "Tax",          "x": 320, "y": 260, "w": 120, "h": 56, "color": "#ffffff"},
    "supplier":     {"label": "Supplier",     "x": 460, "y": 260, "w": 120, "h": 56, "color": "#ffffff"},
    "accounting":   {"label": "Accounting",   "x": 600, "y": 260, "w": 120, "h": 56, "color": "#ffffff"},
    "hr":           {"label": "HR & Payroll", "x": 740, "y": 260, "w": 120, "h": 56, "color": "#ffffff"},
    "notification": {"label": "Notification", "x": 880, "y": 140, "w": 120, "h": 56, "color": "#ffffff"},
    "reporting":    {"label": "Reporting",    "x": 880, "y": 260, "w": 120, "h": 56, "color": "#ffffff"},
}

# Static connector edges (from -> to) drawn on the board
BUSINESS_EDGES: list[tuple[str, str]] = [
    ("storefront", "orders"),
    ("orders", "inventory"),
    ("inventory", "fulfillment"),
    ("fulfillment", "shipping"),
    ("shipping", "customer_comms"),
    ("orders", "payments"),
    ("payments", "finance"),
    ("inventory", "suppliers"),
    ("suppliers", "inventory"),
    ("finance", "people"),
    ("orders", "customer_comms"),
]

MICROSERVICE_EDGES: list[tuple[str, str]] = [
    ("website", "gateway"),
    ("gateway", "customer"),
    ("gateway", "product"),
    ("gateway", "order"),
    ("order", "inventory"),
    ("order", "payment"),
    ("order", "tax"),
    ("inventory", "fulfillment"),
    ("fulfillment", "shipping"),
    ("shipping", "notification"),
    ("order", "notification"),
    ("payment", "accounting"),
    ("tax", "accounting"),
    ("supplier", "inventory"),
    ("accounting", "reporting"),
    ("order", "reporting"),
    ("gateway", "supplier"),
    ("gateway", "hr"),
    ("product", "order"),
]

# Animated flow sequences keyed by event type
BUSINESS_FLOWS: dict[str, list[tuple[str, str]]] = {
    "order_created": [
        ("storefront", "orders"),
        ("orders", "inventory"),
        ("orders", "payments"),
        ("payments", "finance"),
        ("inventory", "fulfillment"),
        ("fulfillment", "shipping"),
        ("shipping", "customer_comms"),
    ],
    "order_confirmed": [
        ("orders", "inventory"),
        ("orders", "customer_comms"),
    ],
    "order_fulfilled": [
        ("inventory", "fulfillment"),
        ("fulfillment", "shipping"),
    ],
    "supplier_restock": [
        ("suppliers", "inventory"),
        ("finance", "suppliers"),
    ],
    "payroll": [
        ("finance", "people"),
    ],
}

MICROSERVICE_FLOWS: dict[str, list[tuple[str, str]]] = {
    "order_created": [
        ("website", "gateway"),
        ("gateway", "customer"),
        ("gateway", "product"),
        ("gateway", "order"),
        ("order", "payment"),
        ("order", "tax"),
        ("order", "inventory"),
        ("inventory", "fulfillment"),
        ("fulfillment", "shipping"),
        ("order", "notification"),
        ("payment", "accounting"),
        ("order", "reporting"),
    ],
    "order_confirmed": [
        ("gateway", "order"),
        ("order", "inventory"),
        ("order", "notification"),
    ],
    "supplier_po": [
        ("gateway", "supplier"),
        ("supplier", "inventory"),
    ],
}


# Per-node callout text when a box lights up (placeholders: total, oid, po)
BUSINESS_NODE_BLURBS: dict[str, dict[str, str]] = {
    "order_created": {
        "storefront": "Order placed for ${total}",
        "orders": "Order #{oid} recorded",
        "inventory": "Stock reserved",
        "payments": "Payment authorized — ${total}",
        "finance": "Revenue booked",
        "fulfillment": "Pick list created",
        "shipping": "Shipping label generated",
        "customer_comms": "Confirmation email sent",
    },
    "order_confirmed": {
        "orders": "Order #{oid} confirmed",
        "inventory": "Reservation updated",
        "customer_comms": "Status update sent",
    },
    "order_fulfilled": {
        "inventory": "Items picked from stock",
        "fulfillment": "Order packed",
        "shipping": "Out for delivery",
    },
    "supplier_restock": {
        "suppliers": "Inbound shipment — {po}",
        "inventory": "Stock levels updated",
        "finance": "Supplier payment scheduled",
    },
    "payroll": {
        "finance": "Payroll funds allocated",
        "people": "Biweekly payroll processed",
    },
}

MICROSERVICE_NODE_BLURBS: dict[str, dict[str, str]] = {
    "order_created": {
        "website": "Checkout complete — ${total}",
        "gateway": "Request routed",
        "customer": "Customer profile linked",
        "product": "Line items priced",
        "order": "Order #{oid} created",
        "payment": "Payment authorized — ${total}",
        "tax": "Tax calculated",
        "inventory": "Inventory reserved",
        "fulfillment": "Fulfillment queued",
        "shipping": "Carrier assigned",
        "notification": "Customer notified",
        "accounting": "Ledger updated",
        "reporting": "Metrics updated",
    },
    "order_confirmed": {
        "gateway": "Order status polled",
        "order": "Order #{oid} confirmed",
        "inventory": "Stock check passed",
        "notification": "Update queued",
    },
    "order_fulfilled": {
        "inventory": "Pick confirmed",
        "fulfillment": "Package sealed",
        "shipping": "Tracking number issued",
    },
    "supplier_po": {
        "gateway": "PO request received",
        "supplier": "Purchase order — {po}",
        "inventory": "Inbound stock received",
    },
}


def build_node_blurbs(view: str, event_key: str, context: dict[str, str]) -> dict[str, str]:
    templates = BUSINESS_NODE_BLURBS if view == "business" else MICROSERVICE_NODE_BLURBS
    event_templates = templates.get(event_key, {})
    blurbs: dict[str, str] = {}
    for node, tmpl in event_templates.items():
        try:
            blurbs[node] = tmpl.format(**context)
        except KeyError:
            blurbs[node] = tmpl
    return blurbs


def topology_payload(view: str) -> dict:
    if view == "business":
        return {
            "nodes": BUSINESS_NODES,
            "edges": [{"from": a, "to": b} for a, b in BUSINESS_EDGES],
        }
    return {
        "nodes": MICROSERVICE_NODES,
        "edges": [{"from": a, "to": b} for a, b in MICROSERVICE_EDGES],
    }
