"""
MongoDB — три коллекции:

  hosts    — инвентарь серверов (available / in_use / unreachable)
  clusters — кластеры хранилищ  (deploying / ready / scaling / deleting / failed)
  jobs     — задачи Ansible     (pending / running / success / failed)

Связи:
  hosts.cluster_id    → clusters.cluster_id
  jobs.cluster_id     → clusters.cluster_id
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


def _db():
    return get_client()[settings.MONGODB_DB]


def get_hosts_collection()    -> AsyncIOMotorCollection: return _db()["hosts"]
def get_clusters_collection() -> AsyncIOMotorCollection: return _db()["clusters"]
def get_jobs_collection()     -> AsyncIOMotorCollection: return _db()["jobs"]


async def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def create_indexes() -> None:
    """Идемпотентное создание индексов при старте приложения."""

    # hosts
    h = get_hosts_collection()
    await h.create_index("host_id",    unique=True)
    await h.create_index("ip",         unique=True)
    await h.create_index("status")
    await h.create_index("cluster_id")   # быстро найти все хосты кластера

    # clusters
    c = get_clusters_collection()
    await c.create_index("cluster_id", unique=True)
    await c.create_index("status")
    await c.create_index("engine")
    await c.create_index("created_at")

    # jobs
    j = get_jobs_collection()
    await j.create_index("job_id",     unique=True)
    await j.create_index("cluster_id")   # история задач кластера
    await j.create_index("status")
    await j.create_index("created_at")

