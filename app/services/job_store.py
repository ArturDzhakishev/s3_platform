"""Job store — CRUD для коллекции jobs."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any
from app.db.mongo import get_jobs_collection
from app.schemas.enums import JobStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_job(
    job_id:     str,
    cluster_id: str,
    engine:     str,
    job_type:   str,
    playbook:   str,
    extra_vars: dict[str, Any],
) -> str:
    await get_jobs_collection().insert_one({
        "job_id":      job_id,
        "cluster_id":  cluster_id,
        "engine":      engine,
        "job_type":    job_type,
        "status":      JobStatus.pending.value,
        "playbook":    playbook,
        "extra_vars":  extra_vars,
        "log":         None,
        "return_code": None,
        "created_at":  _now(),
        "started_at":  None,
        "finished_at": None,
    })
    return job_id


async def set_running(job_id: str) -> None:
    await get_jobs_collection().update_one(
        {"job_id": job_id},
        {"$set": {"status": JobStatus.running.value, "started_at": _now()}},
    )


async def set_finished(job_id: str, rc: int, log: str) -> None:
    status = JobStatus.success.value if rc == 0 else JobStatus.failed.value
    await get_jobs_collection().update_one(
        {"job_id": job_id},
        {"$set": {"status": status, "return_code": rc, "log": log, "finished_at": _now()}},
    )


async def get_job(job_id: str) -> dict | None:
    return await get_jobs_collection().find_one({"job_id": job_id}, {"_id": 0})


async def list_jobs(cluster_id: str | None = None, status: str | None = None, limit: int = 50) -> list[dict]:
    filt: dict = {}
    if cluster_id: filt["cluster_id"] = cluster_id
    if status:     filt["status"] = status
    cursor = get_jobs_collection().find(filt, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)