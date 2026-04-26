"""
Job store — все операции с MongoDB-коллекцией jobs.

Слой намеренно тонкий: только запись/чтение документов.
Бизнес-логика находится в ansible_runner.py и эндпоинтах.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.db.mongo import get_jobs_collection
from app.schemas.enums import JobStatus, JobType, StorageEngine


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_job(
    engine: StorageEngine,
    job_type: JobType,
    playbook: str,
    hosts: list[dict],
    extra_vars: dict[str, Any],
) -> str:
    """Создать документ Job со статусом pending. Вернуть job_id."""
    job_id = str(uuid.uuid4())
    doc = {
        "job_id": job_id,
        "engine": engine,
        "job_type": job_type,
        "status": JobStatus.pending,
        "playbook": playbook,
        "hosts": hosts,
        "extra_vars": extra_vars,
        "log": None,
        "return_code": None,
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
    }
    await get_jobs_collection().insert_one(doc)
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
        {
            "$set": {
                "status": status,
                "return_code": rc,
                "log": log,
                "finished_at": _now(),
            }
        },
    )


async def get_job(job_id: str) -> dict | None:
    doc = await get_jobs_collection().find_one(
        {"job_id": job_id}, {"_id": 0}
    )
    return doc


async def list_jobs(status: str | None = None, limit: int = 50) -> list[dict]:
    filt = {}
    if status:
        filt["status"] = status
    cursor = get_jobs_collection().find(filt, {"_id": 0}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)