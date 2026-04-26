"""
Pydantic-схемы для документа Job в MongoDB.

Структура документа в коллекции jobs:
{
    "job_id":    "uuid4",
    "engine":    "ceph" | "seaweedfs" | "garage",
    "job_type":  "deploy" | "scale" | "teardown",
    "status":    "pending" | "running" | "success" | "failed",
    "playbook":  "deploy_ceph.yml",
    "hosts":     [...],
    "extra_vars": {...},
    "log":        "ansible stdout...",
    "return_code": 0,
    "created_at":  datetime,
    "started_at":  datetime | null,
    "finished_at": datetime | null
}
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.enums import JobStatus, JobType, StorageEngine


class JobCreate(BaseModel):
    engine: StorageEngine
    job_type: JobType
    hosts: list[dict[str, Any]]
    extra_vars: dict[str, Any] = Field(default_factory=dict)


class JobDocument(BaseModel):
    job_id: str
    engine: StorageEngine
    job_type: JobType
    status: JobStatus
    playbook: str
    hosts: list[dict[str, Any]]
    extra_vars: dict[str, Any]
    log: str | None = None
    return_code: int | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobStatusResponse(BaseModel):
    job_id: str
    engine: StorageEngine
    job_type: JobType
    status: JobStatus
    playbook: str
    return_code: int | None = None
    log: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: JobStatus
    playbook: str
    message: str = "Плейбук запущен. Отслеживайте статус через GET /api/v1/jobs/{job_id}"
