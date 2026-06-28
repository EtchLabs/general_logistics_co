from fastapi import APIRouter, Query

from app.db.mongo import get_mongo_db
from app.models.schemas import NotificationListOut, NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListOut)
async def list_notifications(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    db = get_mongo_db()
    cursor = db.notification_log.find().sort("created_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)

    notifications = [
        NotificationOut(
            id=str(doc["_id"]),
            channel=doc["channel"],
            event_type=doc["event_type"],
            payload=doc.get("payload", {}),
            status=doc.get("status", "received"),
            created_at=doc["created_at"],
        )
        for doc in docs
    ]

    total = await db.notification_log.count_documents({})
    return {"notifications": notifications, "total": total, "limit": limit}
