from datetime import UTC, datetime

from bson import ObjectId
from fastapi import APIRouter, HTTPException

from app.db.mongo import get_mongo_db
from app.models.schemas import CategoryCreate, CategoryOut, CategoryUpdate
from app.services.product_service import _category_out, get_category_or_404

router = APIRouter(prefix="/categories", tags=["categories"])


@router.post("", response_model=CategoryOut, status_code=201)
async def create_category(payload: CategoryCreate) -> CategoryOut:
    db = get_mongo_db()
    existing = await db.categories.find_one({"slug": payload.slug})
    if existing:
        raise HTTPException(status_code=409, detail="Category slug already exists")
    if payload.parent_id:
        await get_category_or_404(payload.parent_id)
    now = datetime.now(UTC)
    doc = {
        "name": payload.name,
        "slug": payload.slug,
        "parent_id": payload.parent_id,
        "description": payload.description,
        "is_active": True,
        "created_at": now,
    }
    result = await db.categories.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _category_out(doc)


@router.get("", response_model=list[CategoryOut])
async def list_categories(active_only: bool = True) -> list[CategoryOut]:
    query: dict = {"is_active": True} if active_only else {}
    cursor = get_mongo_db().categories.find(query).sort("name", 1)
    return [_category_out(doc) async for doc in cursor]


@router.get("/{category_id}", response_model=CategoryOut)
async def get_category(category_id: str) -> CategoryOut:
    doc = await get_category_or_404(category_id)
    return _category_out(doc)


@router.patch("/{category_id}", response_model=CategoryOut)
async def update_category(category_id: str, payload: CategoryUpdate) -> CategoryOut:
    doc = await get_category_or_404(category_id)
    updates = payload.model_dump(exclude_unset=True)
    if "slug" in updates:
        existing = await get_mongo_db().categories.find_one(
            {"slug": updates["slug"], "_id": {"$ne": ObjectId(category_id)}}
        )
        if existing:
            raise HTTPException(status_code=409, detail="Category slug already exists")
    if updates.get("parent_id"):
        await get_category_or_404(updates["parent_id"])
    if updates:
        await get_mongo_db().categories.update_one(
            {"_id": ObjectId(category_id)}, {"$set": updates}
        )
        doc.update(updates)
    return _category_out(doc)
