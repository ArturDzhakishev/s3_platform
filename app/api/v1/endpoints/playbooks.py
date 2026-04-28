"""
Вспомогательные endpoints: ping, список плейбуков, задачи.
"""
from __future__ import annotations
import os
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.core.config import get_settings
from app.schemas.enums import JobStatus
from app.schemas.job import JobStatusResponse
from app.services.ansible_runner import ping_host
from app.services.job_store import get_job, list_jobs
from app.services.host_store import list_hosts as _list_hosts, get_host
from app.schemas.host import HostResponse

router = APIRouter(tags=["tools"])
settings = get_settings()


# ── GET /jobs ─────────────────────────────────────────────────────────────────

@router.get("/jobs", tags=["jobs"])
async def list_jobs_endpoint(
    status: JobStatus | None = Query(default=None),
    limit:  int              = Query(default=50, ge=1, le=200),
):
    return await list_jobs(status=status.value if status else None, limit=limit)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse, tags=["jobs"])
async def get_job_endpoint(job_id: str):
    doc = await get_job(job_id)
    if not doc:
        raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND", "message": f"Job {job_id} не найден"})
    return JobStatusResponse(**doc)


# ── GET /hosts ────────────────────────────────────────────────────────────────

@router.get("/hosts", response_model=list[HostResponse], tags=["hosts"])
async def list_hosts_endpoint(status: str | None = Query(default=None)):
    docs = await _list_hosts(status=status)
    return [HostResponse(**d) for d in docs]


@router.get("/hosts/{host_id}", response_model=HostResponse, tags=["hosts"])
async def get_host_endpoint(host_id: str):
    doc = await get_host(host_id)
    if not doc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Host {host_id} не найден"})
    return HostResponse(**doc)


# ── POST /ping ────────────────────────────────────────────────────────────────

class PingRequest(BaseModel):
    ip:                  str
    ssh_user:            str = "ubuntu"
    ssh_port:            int = 22
    ssh_private_key_path: str | None = None

class PingResponse(BaseModel):
    reachable: bool
    ping_ms:   float | None = None
    error:     str | None   = None

@router.post("/ping", response_model=PingResponse, tags=["tools"])
async def ping_endpoint(body: PingRequest):
    reachable, ms, error = await ping_host(body.ip, body.ssh_user, body.ssh_port, body.ssh_private_key_path)
    return PingResponse(reachable=reachable, ping_ms=ms, error=error)


# ── GET /playbooks ────────────────────────────────────────────────────────────

@router.get("/playbooks", tags=["tools"])
async def list_playbooks():
    d = settings.ANSIBLE_PLAYBOOKS_DIR
    if not os.path.isdir(d):
        return {"playbooks": [], "playbooks_dir": d}
    files = []
    for root, _, fnames in os.walk(d):
        for f in fnames:
            if f.endswith(".yml"):
                rel = os.path.relpath(os.path.join(root, f), d)
                files.append(rel)
    return {"playbooks": sorted(files), "playbooks_dir": d}
