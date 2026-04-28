"""
Clusters endpoints.

POST /clusters        — создать кластер и запустить деплой
GET  /clusters        — список кластеров (фильтр: engine, status)
GET  /clusters/{id}   — один кластер
DELETE /clusters/{id} — teardown
GET  /clusters/{id}/jobs — история задач кластера
"""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.schemas.enums import ClusterStatus, StorageEngine
from app.schemas.cluster import ClusterResponse
from app.schemas.job import JobAcceptedResponse
from app.services.ansible_runner import run_deploy_async, run_teardown_async
from app.services.cluster_store import get_cluster, list_clusters
from app.services.job_store import list_jobs
from app.schemas.enums import JobStatus

router = APIRouter(prefix="/clusters", tags=["clusters"])


class HostIn(BaseModel):
    label:               str         = Field(..., examples=["node-master"])
    ip:                  str         = Field(..., examples=["192.168.1.110"])
    ssh_user:            str         = Field(default="ubuntu")
    ssh_port:            int         = Field(default=22, ge=1, le=65535)
    ssh_private_key_path: str | None = None
    role:                str         = Field(default="worker", examples=["master", "worker"])


class CreateClusterRequest(BaseModel):
    name:       str              = Field(..., examples=["prod-ceph-01"])
    engine:     StorageEngine
    hosts:      list[HostIn]    = Field(..., min_length=1)
    extra_vars: dict[str, Any]  = Field(default_factory=dict)


# ── POST /clusters ────────────────────────────────────────────────────────────

@router.post("", status_code=202, response_model=JobAcceptedResponse)
async def create_cluster(body: CreateClusterRequest):
    hosts_payload = [h.model_dump() for h in body.hosts]
    # Первый хост автоматически получает role=master если не указан
    if hosts_payload and hosts_payload[0].get("role") == "worker":
        hosts_payload[0]["role"] = "master"

    try:
        cluster_id, job_id = await run_deploy_async(
            engine=body.engine.value,
            hosts=hosts_payload,
            extra_vars=body.extra_vars,
            name=body.name,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "PLAYBOOK_NOT_FOUND", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "ERROR", "message": str(e)})

    return JobAcceptedResponse(
        job_id=job_id,
        cluster_id=cluster_id,
        status=JobStatus.pending,
        playbook=f"deploy_{body.engine.value}.yml",
    )


# ── GET /clusters ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[ClusterResponse])
async def get_clusters(
    engine: StorageEngine | None = Query(default=None),
    status: ClusterStatus | None = Query(default=None),
):
    docs = await list_clusters(
        engine=engine.value if engine else None,
        status=status.value if status else None,
    )
    return [ClusterResponse(**d) for d in docs]


# ── GET /clusters/{cluster_id} ────────────────────────────────────────────────

@router.get("/{cluster_id}", response_model=ClusterResponse)
async def get_cluster_endpoint(cluster_id: str):
    doc = await get_cluster(cluster_id)
    if not doc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Кластер {cluster_id} не найден"})
    return ClusterResponse(**doc)


# ── DELETE /clusters/{cluster_id} ─────────────────────────────────────────────

@router.delete("/{cluster_id}", status_code=202)
async def delete_cluster_endpoint(cluster_id: str):
    doc = await get_cluster(cluster_id)
    if not doc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Кластер {cluster_id} не найден"})
    if doc["status"] == ClusterStatus.deleting.value:
        raise HTTPException(status_code=409, detail={"code": "ALREADY_DELETING", "message": "Кластер уже удаляется"})

    # Восстановить список хостов из коллекции hosts для inventory
    from app.services.host_store import list_hosts
    hosts = await list_hosts(cluster_id=cluster_id)

    try:
        job_id = await run_teardown_async(
            cluster_id=cluster_id,
            engine=doc["engine"],
            hosts=hosts,
            extra_vars=doc.get("extra_vars", {}),
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "PLAYBOOK_NOT_FOUND", "message": str(e)})

    return {"job_id": job_id, "cluster_id": cluster_id, "status": "pending", "message": "Teardown запущен"}


# ── GET /clusters/{cluster_id}/jobs ───────────────────────────────────────────

@router.get("/{cluster_id}/jobs")
async def get_cluster_jobs(cluster_id: str, limit: int = Query(default=20, ge=1, le=100)):
    doc = await get_cluster(cluster_id)
    if not doc:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Кластер {cluster_id} не найден"})
    return await list_jobs(cluster_id=cluster_id, limit=limit)
