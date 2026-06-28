import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.mongo import get_mongo_db
from app.db.postgres import get_session
from app.models.postgres import BulkDiscountTier, SkuPricing
from app.models.schemas import (
    BulkDiscountTierCreate,
    BulkDiscountTierOut,
    PriceCalculationOut,
    ProductCreate,
    ProductDetailOut,
    ProductOut,
    ProductUpdate,
    SkuPricingCreate,
    SkuPricingOut,
    SkuPricingUpdate,
    SkuProcurementOut,
    json_dumps,
)
from app.services.product_service import (
    apply_bulk_discount,
    build_product_detail,
    cache_delete_pattern,
    cache_get,
    cache_set,
    effective_unit_price,
    get_product_or_404,
    get_sku_pricing_or_404,
    get_variants_for_product,
    validate_coupon,
    _product_out,
)

router = APIRouter(tags=["products"])


@router.post("/products", response_model=ProductDetailOut, status_code=201)
async def create_product(
    payload: ProductCreate,
    session: AsyncSession = Depends(get_session),
) -> ProductDetailOut:
    db = get_mongo_db()
    if await db.products.find_one({"slug": payload.slug}):
        raise HTTPException(status_code=409, detail="Product slug already exists")
    for variant in payload.variants:
        if await db.product_variants.find_one({"sku": variant.sku}):
            raise HTTPException(status_code=409, detail=f"SKU already exists: {variant.sku}")

    now = datetime.now(UTC)
    product_doc = {
        "name": payload.name,
        "slug": payload.slug,
        "description": payload.description,
        "category_id": payload.category_id,
        "images": payload.images,
        "attributes": payload.attributes,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    result = await db.products.insert_one(product_doc)
    product_id = str(result.inserted_id)
    product_doc["_id"] = result.inserted_id

    variant_docs = []
    for variant in payload.variants:
        variant_docs.append(
            {
                "product_id": product_id,
                "sku": variant.sku,
                "attributes": variant.attributes,
                "image_url": variant.image_url,
                "created_at": now,
            }
        )
    if variant_docs:
        await db.product_variants.insert_many(variant_docs)

    await cache_delete_pattern("products:")
    return await build_product_detail(session, product_doc, variant_docs)


@router.get("/products", response_model=list[ProductOut])
async def search_products(
    q: str | None = None,
    category_id: str | None = None,
    active_only: bool = True,
    session: AsyncSession = Depends(get_session),
) -> list[ProductOut]:
    cache_key = f"products:search:{q}:{category_id}:{active_only}"
    cached = await cache_get(cache_key)
    if cached:
        return [ProductOut.model_validate(item) for item in json.loads(cached)]

    query: dict = {"is_active": True} if active_only else {}
    if category_id:
        query["category_id"] = category_id
    if q:
        query["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]

    db = get_mongo_db()
    products: list[ProductOut] = []
    async for doc in db.products.find(query).sort("name", 1).limit(100):
        variants = await get_variants_for_product(str(doc["_id"]))
        products.append(_product_out(doc, variants))

    await cache_set(cache_key, json_dumps([p.model_dump() for p in products]))
    return products


@router.get("/products/sku/{sku}", response_model=ProductDetailOut)
async def get_product_by_sku(
    sku: str,
    session: AsyncSession = Depends(get_session),
) -> ProductDetailOut:
    variant = await get_mongo_db().product_variants.find_one({"sku": sku})
    if variant is None:
        raise HTTPException(status_code=404, detail="SKU not found")
    return await get_product(variant["product_id"], session)


@router.get("/products/sku/{sku}/procurement", response_model=SkuProcurementOut)
async def get_sku_procurement(
    sku: str,
    session: AsyncSession = Depends(get_session),
) -> SkuProcurementOut:
    variant = await get_mongo_db().product_variants.find_one({"sku": sku})
    if variant is None:
        raise HTTPException(status_code=404, detail="SKU not found")
    doc = await get_product_or_404(variant["product_id"])
    pricing = await get_sku_pricing_or_404(session, sku)

    supplier_name: str | None = None
    lead_time_days = 7
    if pricing.supplier_id:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{settings.supplier_service_url}/suppliers/{pricing.supplier_id}"
            )
            if response.status_code == 200:
                supplier_data = response.json()
                supplier_name = supplier_data.get("name")
                lead_time_days = supplier_data.get("lead_time_days", 7)

    reorder_point = pricing.reorder_threshold or 200
    reorder_quantity = max(reorder_point * 2, 500) if reorder_point else 500

    return SkuProcurementOut(
        sku=sku,
        product_name=doc["name"],
        preferred_supplier_id=pricing.supplier_id,
        preferred_supplier_name=supplier_name,
        unit_cost=pricing.cost_basis,
        lead_time_days=lead_time_days,
        reorder_point=reorder_point,
        reorder_quantity=reorder_quantity,
    )


@router.get("/products/{product_id}", response_model=ProductDetailOut)
async def get_product(
    product_id: str,
    session: AsyncSession = Depends(get_session),
) -> ProductDetailOut:
    cache_key = f"products:detail:{product_id}"
    cached = await cache_get(cache_key)
    if cached:
        return ProductDetailOut.model_validate_json(cached)

    doc = await get_product_or_404(product_id)
    variants = await get_variants_for_product(product_id)
    detail = await build_product_detail(session, doc, variants)
    await cache_set(cache_key, detail.model_dump_json())
    return detail


@router.patch("/products/{product_id}", response_model=ProductDetailOut)
async def update_product(
    product_id: str,
    payload: ProductUpdate,
    session: AsyncSession = Depends(get_session),
) -> ProductDetailOut:
    doc = await get_product_or_404(product_id)
    updates = payload.model_dump(exclude_unset=True)
    if "slug" in updates:
        existing = await get_mongo_db().products.find_one(
            {"slug": updates["slug"], "_id": {"$ne": ObjectId(product_id)}}
        )
        if existing:
            raise HTTPException(status_code=409, detail="Product slug already exists")
    updates["updated_at"] = datetime.now(UTC)
    if updates:
        await get_mongo_db().products.update_one(
            {"_id": ObjectId(product_id)}, {"$set": updates}
        )
        doc.update(updates)
    variants = await get_variants_for_product(product_id)
    await cache_delete_pattern("products:")
    return await build_product_detail(session, doc, variants)


@router.post("/pricing/{sku}", response_model=SkuPricingOut, status_code=201)
async def create_pricing(
    sku: str,
    payload: SkuPricingCreate,
    session: AsyncSession = Depends(get_session),
) -> SkuPricingOut:
    if await get_mongo_db().product_variants.find_one({"sku": sku}) is None:
        raise HTTPException(status_code=404, detail="SKU not found in catalog")
    existing = await session.execute(select(SkuPricing).where(SkuPricing.sku == sku))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Pricing already exists for SKU")
    pricing = SkuPricing(sku=sku, **payload.model_dump())
    session.add(pricing)
    await session.commit()
    await session.refresh(pricing)
    await cache_delete_pattern("products:")
    return SkuPricingOut.model_validate(pricing)


@router.get("/pricing/{sku}", response_model=SkuPricingOut)
async def get_pricing(sku: str, session: AsyncSession = Depends(get_session)) -> SkuPricingOut:
    pricing = await get_sku_pricing_or_404(session, sku)
    return SkuPricingOut.model_validate(pricing)


@router.patch("/pricing/{sku}", response_model=SkuPricingOut)
async def update_pricing(
    sku: str,
    payload: SkuPricingUpdate,
    session: AsyncSession = Depends(get_session),
) -> SkuPricingOut:
    pricing = await get_sku_pricing_or_404(session, sku)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(pricing, field, value)
    await session.commit()
    await session.refresh(pricing)
    await cache_delete_pattern("products:")
    return SkuPricingOut.model_validate(pricing)


@router.post("/pricing/{sku}/bulk-tiers", response_model=BulkDiscountTierOut, status_code=201)
async def add_bulk_tier(
    sku: str,
    payload: BulkDiscountTierCreate,
    session: AsyncSession = Depends(get_session),
) -> BulkDiscountTierOut:
    await get_sku_pricing_or_404(session, sku)
    tier = BulkDiscountTier(sku=sku, **payload.model_dump())
    session.add(tier)
    await session.commit()
    await session.refresh(tier)
    await cache_delete_pattern("products:")
    return BulkDiscountTierOut.model_validate(tier)


@router.get("/pricing/{sku}/bulk-tiers", response_model=list[BulkDiscountTierOut])
async def list_bulk_tiers(
    sku: str,
    session: AsyncSession = Depends(get_session),
) -> list[BulkDiscountTierOut]:
    await get_sku_pricing_or_404(session, sku)
    result = await session.execute(
        select(BulkDiscountTier)
        .where(BulkDiscountTier.sku == sku)
        .order_by(BulkDiscountTier.min_quantity)
    )
    return [BulkDiscountTierOut.model_validate(t) for t in result.scalars().all()]


@router.get("/pricing/{sku}/calculate", response_model=PriceCalculationOut)
async def calculate_price(
    sku: str,
    quantity: int = Query(default=1, ge=1),
    coupon_code: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> PriceCalculationOut:
    pricing = await get_sku_pricing_or_404(session, sku)
    unit_price, _ = effective_unit_price(pricing, quantity)
    unit_price, bulk_pct = await apply_bulk_discount(session, sku, quantity, unit_price)
    subtotal = unit_price * quantity

    coupon_discount = Decimal("0")
    if coupon_code:
        valid, discount, _msg = await validate_coupon(session, coupon_code, subtotal)
        if valid:
            coupon_discount = discount

    total = max(subtotal - coupon_discount, Decimal("0"))
    return PriceCalculationOut(
        sku=sku,
        quantity=quantity,
        unit_price=unit_price,
        subtotal=subtotal,
        bulk_discount_percent=bulk_pct,
        coupon_discount=coupon_discount,
        total=total,
    )
