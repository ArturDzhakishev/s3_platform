"""
Cluster store — все операции с MongoDB-коллекцией clusters.

Cluster store — CRUD для коллекции clusters.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.db.mongo import get_clusters_collection
from app.schemas.enums import ClusterStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_cluster(
    cluster_id:    str,
    name:          str,
    engine:        str,
    host_ids:      list[str],
    extra_vars:    dict[str, Any],
    deploy_job_id: str,
) -> dict:
    doc = {
        "cluster_id":    cluster_id,
        "name":          name,
        "engine":        engine,
        "status":        ClusterStatus.deploying.value,
        "host_ids":      host_ids,
        "node_count":    len(host_ids),
        "extra_vars":    extra_vars,
        "s3_endpoint":   None,
        "credentials":   None,
        "error_msg":     None,
        "deploy_job_id": deploy_job_id,
        "created_at":    _now(),
        "updated_at":    _now(),
    }
    await get_clusters_collection().insert_one(doc)
    return doc


async def set_cluster_ready(cluster_id: str, s3_endpoint: str | None = None) -> None:
    """Деплой прошёл успешно — перевести в ready, записать S3-эндпоинт."""
    await get_clusters_collection().update_one(
        {"cluster_id": cluster_id},
        {"$set": {
            "status":      ClusterStatus.ready.value,
            "s3_endpoint": s3_endpoint,
            "error_msg":   None,
            "updated_at":  _now(),
        }},
    )


async def set_cluster_status(cluster_id: str, status: ClusterStatus, error_msg: str | None = None) -> None:
    upd: dict = {"status": status.value, "updated_at": _now()}
    if error_msg is not None:
        upd["error_msg"] = error_msg
    await get_clusters_collection().update_one({"cluster_id": cluster_id}, {"$set": upd})


async def delete_cluster(cluster_id: str) -> None:
    await get_clusters_collection().delete_one({"cluster_id": cluster_id})


async def get_cluster(cluster_id: str) -> dict | None:
    return await get_clusters_collection().find_one({"cluster_id": cluster_id}, {"_id": 0})


async def list_clusters(engine: str | None = None, status: str | None = None) -> list[dict]:
    filt: dict = {}
    if engine:  filt["engine"] = engine
    if status:  filt["status"] = status
    cursor = get_clusters_collection().find(filt, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(length=None)