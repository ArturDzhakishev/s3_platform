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
from app.services.ansible_runner import run_deploy_async, run_teardown_async, run_scale_async
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
    groups:              list[str]   = Field(
        default_factory=list,
        description=(
            "Ansible-группы в которые входит нода. "
            "Если не указано — определяется движком автоматически. "
            "SeaweedFS: seaweedfs, s3, loadbalancer. "
            "Ceph: master, workers, new_workers. "
            "Garage: garage, bootstrap."
        ),
        examples=[["seaweedfs", "s3"], ["seaweedfs"], ["seaweedfs", "loadbalancer"]],
    )

class CreateClusterRequest(BaseModel):
    name:       str              = Field(..., examples=["prod-ceph-01"])
    engine:     StorageEngine
    hosts:      list[HostIn]    = Field(..., min_length=1)
    extra_vars: dict[str, Any]  = Field(default_factory=dict)

class ScaleRequest(BaseModel):
    """
    Только новые ноды для добавления.
    Бэкенд сам достаёт существующие ноды кластера из MongoDB
    и объединяет со списком новых.
    """
    new_hosts: list[HostIn] = Field(..., min_length=1)

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

# ── POST /clusters/{cluster_id}/scale ─────────────────────────────────────────

@router.post("/{cluster_id}/scale", status_code=202)
async def scale_cluster(cluster_id: str, body: ScaleRequest):
    doc = await get_cluster(cluster_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"Кластер {cluster_id} не найден"},
        )

    # 409 — кластер должен быть в статусе ready
    if doc["status"] != ClusterStatus.ready.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CLUSTER_NOT_READY",
                "message": f"Масштабирование возможно только в статусе ready, сейчас: {doc['status']}",
            },
        )

    # Достать существующие ноды кластера из MongoDB
    from app.services.host_store import list_hosts
    existing_hosts = await list_hosts(cluster_id=cluster_id)

    # Проверить что новые ноды не дублируют существующие по IP
    existing_ips = {h["ip"] for h in existing_hosts}
    new_hosts_payload = [h.model_dump() for h in body.new_hosts]
    duplicates = [h["ip"] for h in new_hosts_payload if h["ip"] in existing_ips]
    if duplicates:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "HOST_ALREADY_IN_CLUSTER",
                "message": f"Хосты уже в кластере: {', '.join(duplicates)}",
            },
        )

    # Объединить: старые ноды + новые
    all_hosts = existing_hosts + new_hosts_payload

    try:
        job_id = await run_scale_async(
            cluster_id=cluster_id,
            engine=doc["engine"],
            hosts=all_hosts,          
            new_hosts=new_hosts_payload,  
            extra_vars=doc.get("extra_vars", {}),
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail={"code": "PLAYBOOK_NOT_FOUND", "message": str(e)},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "ERROR", "message": str(e)},
        )

    return {
        "job_id":     job_id,
        "cluster_id": cluster_id,
        "status":     "pending",
        "playbook":   f"scale_{doc['engine']}.yml",
        "message":    "Масштабирование запущено",
    }

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
