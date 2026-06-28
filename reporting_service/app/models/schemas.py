from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class SalesSummaryOut(BaseModel):
    order_count: int
    total_revenue: Decimal
    average_order_value: Decimal
    generated_at: datetime
    source: str = "order_service"


class InventorySummaryOut(BaseModel):
    product_count: int
    active_products: int
    categories: dict[str, int] = Field(default_factory=dict)
    generated_at: datetime
    source: str = "product_service"
