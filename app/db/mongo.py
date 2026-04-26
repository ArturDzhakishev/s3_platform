"""
MongoDB connection via Motor (async driver).

Единственный клиент создаётся при старте приложения в lifespan.
Все коллекции доступны через get_jobs_collection().

EXTEND: добавить коллекции clusters, hosts при расширении архитектуры.
"""
from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from app.core.config import get_settings

settings = get_settings()

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGODB_URL)
    return _client


def get_jobs_collection() -> AsyncIOMotorCollection:
    return get_client()[settings.MONGODB_DB]["jobs"]


async def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def create_indexes() -> None:
    """Создать индексы при старте. Идемпотентно."""
    jobs = get_jobs_collection()
    await jobs.create_index("job_id", unique=True)
    await jobs.create_index("status")
    await jobs.create_index("created_at")
