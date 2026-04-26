"""
Playbook endpoints — асинхронная версия с MongoDB.

Изменения по сравнению с MVP:
  POST /run    → 202 Accepted + job_id  (раньше было 200 + полный лог)
  GET  /jobs   → список задач из MongoDB
  GET  /jobs/{job_id} → статус и лог конкретной задачи
"""
from __future__ import annotations

import os
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.config import get_settings
from app.schemas.enums import JobStatus, JobType, StorageEngine
from app.schemas.job import JobAcceptedResponse, JobStatusResponse
from app.schemas.playbook import HostEntry, RunPlaybookRequest
from app.services.ansible_runner import ping_host, run_playbook_async
from app.services.job_store import get_job, list_jobs

router = APIRouter(tags=["playbooks"])
settings = get_settings()


# ── POST /run ─────────────────────────────────────────────────────────────────

@router.post(
    "/run",
    response_model=JobAcceptedResponse,
    status_code=202,
    summary="Запустить плейбук асинхронно",
    description=(
        "Создаёт Job в MongoDB, запускает плейбук в фоне и немедленно "
        "возвращает job_id. Статус отслеживается через GET /api/v1/jobs/{job_id}."
    ),
)
async def run_playbook_endpoint(body: RunPlaybookRequest) -> PlaybookResult:
    hosts_payload = [
        {
            "ip": h.ip,
            "ssh_user": h.ssh_user,
            "ssh_port": h.ssh_port,
            "ssh_key_path": h.ssh_private_key_path,
        }
        for h in body.hosts
    ]

    try:
        job_id = await run_playbook_async(
            engine=body.engine.value,
            job_type=body.job_type.value,
            hosts=hosts_payload,
            extra_vars=body.extra_vars,
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={"code": "PLAYBOOK_NOT_FOUND", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "RUNNER_ERROR", "message": str(e)},
        )

    playbook_name = f"{body.job_type.value}_{body.engine.value}.yml"
    return JobAcceptedResponse(
        job_id=job_id,
        status=JobStatus.pending,
        playbook=playbook_name,
    )


# ── POST /ping ────────────────────────────────────────────────────────────────

class PingRequest(BaseModel):
    host: HostEntry


class PingResponse(BaseModel):
    reachable: bool
    ping_ms: float | None = None
    error: str | None = None


# ── GET /jobs ─────────────────────────────────────────────────────────────────

@router.get(
    "/jobs",
    summary="Список задач",
    description="Последние 50 задач из MongoDB. Фильтр по статусу опционален.",
)
async def list_jobs_endpoint(
    status: JobStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    docs = await list_jobs(
        status=status.value if status else None,
        limit=limit,
    )
    return docs


# ── GET /jobs/{job_id} ────────────────────────────────────────────────────────

@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Статус задачи",
    description="Возвращает текущий статус задачи и лог Ansible по job_id.",
)
async def get_job_endpoint(job_id: str) -> JobStatusResponse:
    doc = await get_job(job_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": f"Job {job_id} не найден"},
        )
    return JobStatusResponse(**doc)


@router.post(
    "/ping",
    response_model=PingResponse,
    summary="Проверить SSH-доступность хоста",
    description="Запускает ansible -m ping. Возвращает время отклика в мс.",
)
async def ping_endpoint(body: PingRequest) -> PingResponse:
    reachable, ms, error = await ping_host(
        ip=body.host.ip,
        ssh_user=body.host.ssh_user,
        ssh_port=body.host.ssh_port,
        key_path=body.host.ssh_private_key_path,
    )
    return PingResponse(reachable=reachable, ping_ms=ms, error=error)


# ── GET /playbooks ────────────────────────────────────────────────────────────

class PlaybookListResponse(BaseModel):
    playbooks: list[str]
    playbooks_dir: str


@router.get(
    "/playbooks",
    response_model=PlaybookListResponse,
    summary="Список доступных плейбуков",
    description="Возвращает .yml файлы из ANSIBLE_PLAYBOOKS_DIR.",
)
async def list_playbooks() -> PlaybookListResponse:
    d = settings.ANSIBLE_PLAYBOOKS_DIR
    if not os.path.isdir(d):
        return PlaybookListResponse(playbooks=[], playbooks_dir=d)
    files = sorted(f for f in os.listdir(d) if f.endswith(".yml"))
    return PlaybookListResponse(playbooks=files, playbooks_dir=d)
