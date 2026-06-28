from datetime import datetime

from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: str
    channel: str
    event_type: str
    payload: dict
    status: str
    created_at: datetime


class NotificationListOut(BaseModel):
    notifications: list[NotificationOut]
    total: int
    limit: int = Field(default=50)
