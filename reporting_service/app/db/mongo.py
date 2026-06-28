from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

_client: AsyncIOMotorClient | None = None


def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongo_uri)
    return _client


def get_mongo_db() -> AsyncIOMotorDatabase:
    settings = get_settings()
    return get_mongo_client()[settings.mongo_db]


async def close_mongo_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
