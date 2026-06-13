"""
Host store — CRUD для коллекции hosts.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.db.mongo import get_hosts_collection
from app.schemas.enums import HostStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def upsert_host(
    ip:                   str,
    label:                str,
    ssh_user:             str,
    ssh_port:             int,
    ssh_private_key:      str | None = None,  # PEM-содержимое — сохраняется в MongoDB
    role:                 str = "worker",
    cluster_id:           str = "",
    zone:                 str | None = None,
    capacity:             str | None = None,
) -> str:
    col = get_hosts_collection()
    existing = await col.find_one({"ip": ip}, {"host_id": 1})

    fields = {
        "label":                label,
        "ssh_user":             ssh_user,
        "ssh_port":             ssh_port,
        "ssh_private_key":      ssh_private_key,   # None если передан путь
        "role":                 role,
        "status":               HostStatus.in_use.value,
        "cluster_id":           cluster_id,
        "updated_at":           _now(),
        "zone":                 zone,
        "capacity":             capacity,
    }

    if existing:
        host_id = existing["host_id"]
        # Не затирать ssh_private_key если новый запрос не передал его
        update = {"$set": fields}
        if not ssh_private_key:
            update["$set"].pop("ssh_private_key")
        await col.update_one({"host_id": host_id}, update)
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


async def list_hosts(
    cluster_id: str | None = None,
    status:     str | None = None,
) -> list[dict]:
    filt: dict = {}
    if cluster_id:
        filt["cluster_id"] = cluster_id
    if status:
        filt["status"] = status
    cursor = get_hosts_collection().find(filt, {"_id": 0}).sort("created_at", 1)
    return await cursor.to_list(length=None)

async def remove_hosts_without_key(cluster_id: str, ips: list[str]) -> int:
    """
    Удаляет хосты кластера по IP у которых нет SSH-ключа.
    Используется перед повторным scale после failed —
    чтобы дать возможность добавить те же ноды с ключом.
    Возвращает количество удалённых документов.
    """
    result = await get_hosts_collection().delete_many({
        "cluster_id": cluster_id,
        "ip":         {"$in": ips},
        "$or": [
            {"ssh_private_key": None},
            {"ssh_private_key": ""},
            {"ssh_private_key": {"$exists": False}},
        ],
    })
    return result.deleted_count
