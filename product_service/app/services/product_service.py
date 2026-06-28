from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from bson import ObjectId
from fastapi import HTTPException
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.mongo import get_mongo_db
from app.db.redis import get_redis
from app.models.postgres import BulkDiscountTier, CouponCode, Promotion, SkuPricing
from app.models.schemas import (
    CategoryOut,
    ProductDetailOut,
    ProductOut,
    SkuPricingOut,
    VariantOut,
    json_dumps,
)


async def ensure_mongo_indexes() -> None:
    db = get_mongo_db()
    await db.categories.create_index("slug", unique=True)
    await db.products.create_index("slug", unique=True)
    await db.products.create_index("category_id")
    await db.product_variants.create_index("sku", unique=True)
    await db.product_variants.create_index("product_id")


async def cache_get(key: str) -> str | None:
    redis: Redis = get_redis()
    return await redis.get(key)


async def cache_set(key: str, value: str, ttl: int | None = None) -> None:
    settings = get_settings()
    redis: Redis = get_redis()
    await redis.set(key, value, ex=ttl or settings.cache_ttl_seconds)


async def cache_delete_pattern(prefix: str) -> None:
    redis: Redis = get_redis()
    async for key in redis.scan_iter(match=f"{prefix}*"):
        await redis.delete(key)


def _category_out(doc: dict) -> CategoryOut:
    return CategoryOut(
        id=str(doc["_id"]),
        name=doc["name"],
        slug=doc["slug"],
        parent_id=doc.get("parent_id"),
        description=doc.get("description"),
        is_active=doc.get("is_active", True),
        created_at=doc["created_at"],
    )


def _product_out(doc: dict, variants: list[dict]) -> ProductOut:
    return ProductOut(
        id=str(doc["_id"]),
        name=doc["name"],
        slug=doc["slug"],
        description=doc.get("description", ""),
        category_id=doc.get("category_id"),
        images=doc.get("images", []),
        attributes=doc.get("attributes", {}),
        variants=[
            VariantOut(
                sku=v["sku"],
                attributes=v.get("attributes", {}),
                image_url=v.get("image_url"),
            )
            for v in variants
        ],
        is_active=doc.get("is_active", True),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


async def get_product_or_404(product_id: str) -> dict:
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=404, detail="Product not found")
    doc = await get_mongo_db().products.find_one({"_id": ObjectId(product_id)})
    if doc is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return doc


async def get_category_or_404(category_id: str) -> dict:
    if not ObjectId.is_valid(category_id):
        raise HTTPException(status_code=404, detail="Category not found")
    doc = await get_mongo_db().categories.find_one({"_id": ObjectId(category_id)})
    if doc is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return doc


async def get_variants_for_product(product_id: str) -> list[dict]:
    cursor = get_mongo_db().product_variants.find({"product_id": product_id})
    return [doc async for doc in cursor]


async def build_product_detail(
    session: AsyncSession,
    doc: dict,
    variants: list[dict],
) -> ProductDetailOut:
    product = _product_out(doc, variants)
    skus = [v["sku"] for v in variants]
    pricing: dict[str, SkuPricingOut] = {}
    if skus:
        result = await session.execute(select(SkuPricing).where(SkuPricing.sku.in_(skus)))
        for row in result.scalars().all():
            pricing[row.sku] = SkuPricingOut.model_validate(row)
    return ProductDetailOut(**product.model_dump(), pricing=pricing)


async def get_sku_pricing_or_404(session: AsyncSession, sku: str) -> SkuPricing:
    result = await session.execute(select(SkuPricing).where(SkuPricing.sku == sku))
    pricing = result.scalar_one_or_none()
    if pricing is None:
        raise HTTPException(status_code=404, detail="SKU pricing not found")
    return pricing


def effective_unit_price(pricing: SkuPricing, quantity: int) -> tuple[Decimal, Decimal]:
    now = datetime.now(UTC)
    price = pricing.msrp
    if pricing.sale_price is not None:
        if pricing.sale_starts_at and now < pricing.sale_starts_at:
            pass
        elif pricing.sale_ends_at and now > pricing.sale_ends_at:
            pass
        else:
            price = pricing.sale_price
    return price, Decimal("0")


async def apply_bulk_discount(
    session: AsyncSession,
    sku: str,
    quantity: int,
    unit_price: Decimal,
) -> tuple[Decimal, Decimal]:
    result = await session.execute(
        select(BulkDiscountTier)
        .where(BulkDiscountTier.sku == sku, BulkDiscountTier.min_quantity <= quantity)
        .order_by(BulkDiscountTier.min_quantity.desc())
    )
    tier = result.scalars().first()
    if tier is None:
        return unit_price, Decimal("0")
    discount_pct = tier.discount_percent
    discounted = unit_price * (Decimal("100") - discount_pct) / Decimal("100")
    return discounted, discount_pct


async def validate_coupon(
    session: AsyncSession,
    code: str,
    subtotal: Decimal,
) -> tuple[bool, Decimal, str]:
    result = await session.execute(
        select(CouponCode, Promotion)
        .join(Promotion, CouponCode.promotion_id == Promotion.id)
        .where(CouponCode.code == code.upper())
    )
    row = result.first()
    if row is None:
        return False, Decimal("0"), "Coupon not found"
    coupon, promotion = row
    now = datetime.now(UTC)
    if not coupon.is_active or not promotion.is_active:
        return False, Decimal("0"), "Coupon is inactive"
    if coupon.max_uses is not None and coupon.current_uses >= coupon.max_uses:
        return False, Decimal("0"), "Coupon usage limit reached"
    if promotion.starts_at and now < promotion.starts_at:
        return False, Decimal("0"), "Promotion has not started"
    if promotion.ends_at and now > promotion.ends_at:
        return False, Decimal("0"), "Promotion has expired"

    if promotion.discount_type == "percent":
        discount = subtotal * promotion.discount_value / Decimal("100")
    else:
        discount = min(promotion.discount_value, subtotal)
    return True, discount, "Coupon applied"
