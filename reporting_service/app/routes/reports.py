from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter

from app.models.schemas import InventorySummaryOut, SalesSummaryOut
from app.services.reporting_service import get_inventory_summary, get_sales_summary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/sales-summary", response_model=SalesSummaryOut)
async def sales_summary() -> dict:
    data = await get_sales_summary()
    return {
        "order_count": data["order_count"],
        "total_revenue": Decimal(data["total_revenue"]),
        "average_order_value": Decimal(data["average_order_value"]),
        "generated_at": datetime.fromisoformat(data["generated_at"]),
        "source": data["source"],
    }


@router.get("/inventory-summary", response_model=InventorySummaryOut)
async def inventory_summary() -> dict:
    data = await get_inventory_summary()
    return {
        "product_count": data["product_count"],
        "active_products": data["active_products"],
        "categories": data["categories"],
        "generated_at": datetime.fromisoformat(data["generated_at"]),
        "source": data["source"],
    }
