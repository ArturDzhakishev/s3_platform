"""
Host store — CRUD для коллекции hosts.

Хост создаётся при POST /run (один раз за каждый уникальный IP).
При повторном запросе с тем же IP — документ обновляется.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.db.mongo import get_hosts_collection
from app.schemas.enums import HostStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def upsert_host(
    ip:                   str,
    label:                str,
    ssh_user:             str,
    ssh_port:             int,
    ssh_private_key_path: str | None,
    role:                 str,
    cluster_id:           str,
    zone:                 str | None = None,
    capacity:             str | None = None,
) -> str:
    """
    Создать хост или обновить существующий по IP.
    Возвращает host_id.
    """
    col = get_hosts_collection()
    existing = await col.find_one({"ip": ip}, {"host_id": 1})

    fields = {
        "label":                label,
        "ssh_user":             ssh_user,
        "ssh_port":             ssh_port,
        "ssh_private_key_path": ssh_private_key_path,
        "role":                 role,
        "status":               HostStatus.in_use.value,
        "cluster_id":           cluster_id,
        "updated_at":           _now(),
        # Garage-специфичные поля — None для других движков
        "zone":                 zone,
        "capacity":             capacity,
    }

    if existing:
        host_id = existing["host_id"]
        await col.update_one({"host_id": host_id}, {"$set": fields})
    else:
        host_id = str(uuid.uuid4())
        await col.insert_one({
            "host_id":    host_id,
            "ip":         ip,
            "created_at": _now(),
            **fields,
        })

    return host_id


async def release_hosts(cluster_id: str) -> None:
    """После teardown: сбросить cluster_id и вернуть статус available."""
    await get_hosts_collection().update_many(
        {"cluster_id": cluster_id},
        {"$set": {
            "status":     HostStatus.available.value,
            "cluster_id": None,
            "updated_at": _now(),
        }},
    )


async def mark_unreachable(ip: str) -> None:
    await get_hosts_collection().update_one(
        {"ip": ip},
        {"$set": {"status": HostStatus.unreachable.value, "updated_at": _now()}},
    )


async def get_host(host_id: str) -> dict | None:
    return await get_hosts_collection().find_one({"host_id": host_id}, {"_id": 0})


async def list_hosts(cluster_id: str | None = None, status: str | None = None) -> list[dict]:
    filt: dict = {}
    if cluster_id:
        filt["cluster_id"] = cluster_id
    if status:
        filt["status"] = status
    cursor = get_hosts_collection().find(filt, {"_id": 0}).sort("created_at", 1)
    return await cursor.to_list(length=None)
