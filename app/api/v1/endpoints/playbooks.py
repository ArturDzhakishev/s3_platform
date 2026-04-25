"""
Playbook endpoints — MVP без БД и Celery.

Три маршрута, покрывающие все типы задач из OpenAPI-спецификации:

  POST /run          — запустить любой плейбук синхронно
  POST /ping         — проверить SSH-доступность хоста
  GET  /playbooks    — список доступных плейбуков

EXTEND: при добавлении БД — каждый маршрут получает db: AsyncSession = Depends(get_db),
        создаёт Job-запись и возвращает job_id вместо полного лога.
EXTEND: при добавлении Celery — run_playbook() заменяется на task.delay(),
        маршрут возвращает 202 Accepted + {job_id, celery_task_id}.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.schemas.enums import JobStatus, JobType, StorageEngine
from app.schemas.playbook import HostEntry, PlaybookResult, RunPlaybookRequest
from app.services.ansible_runner import ping_host, run_playbook

router = APIRouter(tags=["playbooks"])
settings = get_settings()


# ── POST /run ─────────────────────────────────────────────────────────────────

@router.post(
    "/run",
    response_model=PlaybookResult,
    summary="Запустить Ansible-плейбук",
    description=(
        "Синхронно выполняет плейбук и возвращает полный stdout. "
        "Плейбук выбирается автоматически по схеме `{job_type}_{engine}.yml`."
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
        rc, stdout, playbook_name = await run_playbook(
            engine=body.engine.value,
            job_type=body.job_type.value,
            hosts=hosts_payload,
            extra_vars=body.extra_vars,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "PLAYBOOK_NOT_FOUND", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "RUNNER_ERROR", "message": str(e)})

    return PlaybookResult(
        job_type=body.job_type,
        engine=body.engine,
        status=JobStatus.success if rc == 0 else JobStatus.failed,
        playbook=playbook_name,
        log=stdout,
        return_code=rc,
    )


# ── POST /ping ────────────────────────────────────────────────────────────────

class PingRequest(BaseModel):
    host: HostEntry


class PingResponse(BaseModel):
    reachable: bool
    ping_ms: float | None = None
    error: str | None = None


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
