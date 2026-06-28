import json
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=120)
    parent_id: str | None = None
    description: str | None = None


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    slug: str | None = Field(default=None, max_length=120)
    parent_id: str | None = None
    description: str | None = None
    is_active: bool | None = None


class CategoryOut(BaseModel):
    id: str
    name: str
    slug: str
    parent_id: str | None
    description: str | None
    is_active: bool
    created_at: datetime


class VariantCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=50)
    attributes: dict = Field(default_factory=dict)
    image_url: str | None = None


class VariantOut(BaseModel):
    sku: str
    attributes: dict
    image_url: str | None


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=200)
    description: str = ""
    category_id: str | None = None
    images: list[str] = Field(default_factory=list)
    attributes: dict = Field(default_factory=dict)
    variants: list[VariantCreate] = Field(min_length=1)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    slug: str | None = Field(default=None, max_length=200)
    description: str | None = None
    category_id: str | None = None
    images: list[str] | None = None
    attributes: dict | None = None
    is_active: bool | None = None


class SkuProcurementOut(BaseModel):
    sku: str
    product_name: str
    preferred_supplier_id: UUID | None = None
    preferred_supplier_name: str | None = None
    unit_cost: Decimal
    lead_time_days: int
    reorder_point: int
    reorder_quantity: int


class SkuPricingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str
    msrp: Decimal
    sale_price: Decimal | None
    cost_basis: Decimal
    supplier_id: UUID | None
    reorder_threshold: int
    sale_starts_at: datetime | None
    sale_ends_at: datetime | None
    is_active: bool


class SkuPricingCreate(BaseModel):
    msrp: Decimal = Field(gt=0)
    sale_price: Decimal | None = Field(default=None, gt=0)
    cost_basis: Decimal = Field(gt=0)
    supplier_id: UUID | None = None
    reorder_threshold: int = Field(default=0, ge=0)
    sale_starts_at: datetime | None = None
    sale_ends_at: datetime | None = None


class SkuPricingUpdate(BaseModel):
    msrp: Decimal | None = Field(default=None, gt=0)
    sale_price: Decimal | None = Field(default=None, gt=0)
    cost_basis: Decimal | None = Field(default=None, gt=0)
    supplier_id: UUID | None = None
    reorder_threshold: int | None = Field(default=None, ge=0)
    sale_starts_at: datetime | None = None
    sale_ends_at: datetime | None = None
    is_active: bool | None = None


class BulkDiscountTierCreate(BaseModel):
    min_quantity: int = Field(ge=2)
    discount_percent: Decimal = Field(gt=0, le=100)


class BulkDiscountTierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sku: str
    min_quantity: int
    discount_percent: Decimal


class PriceCalculationOut(BaseModel):
    sku: str
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    bulk_discount_percent: Decimal
    coupon_discount: Decimal
    total: Decimal


class PromotionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    discount_type: str = Field(pattern="^(percent|fixed)$")
    discount_value: Decimal = Field(gt=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class PromotionUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    description: str | None = None
    discount_type: str | None = Field(default=None, pattern="^(percent|fixed)$")
    discount_value: Decimal | None = Field(default=None, gt=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None


class PromotionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    discount_type: str
    discount_value: Decimal
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    created_at: datetime


class CouponCreate(BaseModel):
    code: str = Field(min_length=3, max_length=50)
    promotion_id: UUID
    max_uses: int | None = Field(default=None, ge=1)


class CouponOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    promotion_id: UUID
    max_uses: int | None
    current_uses: int
    is_active: bool
    created_at: datetime


class CouponValidateRequest(BaseModel):
    code: str
    subtotal: Decimal = Field(gt=0)


class CouponValidateOut(BaseModel):
    valid: bool
    code: str
    discount_amount: Decimal
    message: str


class ProductOut(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    category_id: str | None
    images: list[str]
    attributes: dict
    variants: list[VariantOut]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductDetailOut(ProductOut):
    pricing: dict[str, SkuPricingOut]


def json_dumps(data: object) -> str:
    return json.dumps(data, default=str)
