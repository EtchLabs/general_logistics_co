import json
import logging
from datetime import UTC, datetime

from app.config import get_settings
from app.db.mongo import get_mongo_db
from app.db.redis import get_redis

logger = logging.getLogger(__name__)


async def ensure_mongo_indexes() -> None:
    db = get_mongo_db()
    await db.notification_log.create_index("created_at")
    await db.notification_log.create_index("channel")
    await db.notification_log.create_index("event_type")


async def log_notification(channel: str, payload: dict, status: str = "received") -> None:
    db = get_mongo_db()
    event_type = channel.split(".", 1)[-1] if "." in channel else channel
    await db.notification_log.insert_one(
        {
            "channel": channel,
            "event_type": event_type,
            "payload": payload,
            "status": status,
            "created_at": datetime.now(UTC),
        }
    )


async def redis_subscriber_loop(stop_event) -> None:
    settings = get_settings()
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.psubscribe(settings.redis_channel_pattern)
    logger.info("Subscribed to Redis pattern: %s", settings.redis_channel_pattern)

    try:
        async for message in pubsub.listen():
            if stop_event.is_set():
                break
            if message["type"] != "pmessage":
                continue

            channel = message["channel"]
            raw_data = message["data"]
            try:
                payload = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
            except json.JSONDecodeError:
                payload = {"raw": raw_data}

            try:
                await log_notification(channel, payload)
                logger.info("Logged notification from channel %s", channel)
            except Exception:
                logger.exception("Failed to log notification from channel %s", channel)
    finally:
        await pubsub.punsubscribe(settings.redis_channel_pattern)
        await pubsub.aclose()
