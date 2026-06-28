from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceDef:
    label: str
    compose_name: str
    port: int
    group: str


SERVICES: tuple[ServiceDef, ...] = (
    ServiceDef("API Gateway", "api_gateway", 8080, "core"),
    ServiceDef("Website", "website", 8000, "core"),
    ServiceDef("Customer", "customer_service", 8001, "commerce"),
    ServiceDef("Product", "product_service", 8002, "commerce"),
    ServiceDef("Order", "order_service", 8003, "commerce"),
    ServiceDef("Inventory", "inventory_service", 8004, "ops"),
    ServiceDef("Fulfillment", "fulfillment_service", 8005, "ops"),
    ServiceDef("Shipping", "shipping_service", 8006, "ops"),
    ServiceDef("Payment", "payment_service", 8007, "finance"),
    ServiceDef("Tax", "tax_service", 8008, "finance"),
    ServiceDef("Supplier", "supplier_service", 8009, "supply"),
    ServiceDef("Accounting", "accounting_service", 8010, "finance"),
    ServiceDef("HR & Payroll", "hr_payroll_service", 8011, "people"),
    ServiceDef("Notification", "notification_service", 8012, "ops"),
    ServiceDef("Reporting", "reporting_service", 8013, "finance"),
    ServiceDef("Customer Sim", "customer_simulator", 8020, "sim"),
    ServiceDef("Supplier Sim", "supplier_simulator", 0, "sim"),
)

LOG_SERVICES: tuple[str, ...] = tuple(s.compose_name for s in SERVICES)
