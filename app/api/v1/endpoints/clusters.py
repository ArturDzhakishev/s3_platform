"""
Clusters endpoints.

POST /clusters              — создать кластер и запустить деплой
GET  /clusters              — список кластеров (фильтр: engine, status)
GET  /clusters/{id}         — один кластер
DELETE /clusters/{id}       — teardown
POST /clusters/{id}/scale   — масштабирование
POST /clusters/{id}/retry   — повторить последнюю упавшую операцию (deploy/scale/teardown)
GET  /clusters/{id}/jobs    — история задач кластера
"""
from __future__ import annotations
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.schemas.enums import ClusterStatus, StorageEngine, JobType
from app.schemas.cluster import ClusterResponse
from app.schemas.job import JobAcceptedResponse
from app.services.ansible_runner import run_deploy_async, run_teardown_async, run_scale_async
from app.services.cluster_store import get_cluster, list_clusters
from app.services.job_store import list_jobs, get_last_failed_job
from app.schemas.enums import JobStatus

router = APIRouter(prefix="/clusters", tags=["clusters"])


class HostIn(BaseModel):
    label:           str        = Field(..., examples=["node-master"])
    ip:              str        = Field(..., examples=["192.168.1.110"])
    ssh_user:        str        = Field(default="ubuntu")
    ssh_port:        int        = Field(default=22, ge=1, le=65535)
    ssh_private_key: str | None = Field(default=None)
    role:    str       = Field(default="worker", examples=["master", "worker"])
    groups:  list[str] = Field(
        default_factory=list,
        description="Ansible-группы в которые входит нода.",
        examples=[["seaweedfs", "s3"], ["seaweedfs"], ["garage"]],
    )
    zone:     str | None = Field(default=None, description="Garage: зона размещения")
    capacity: str | None = Field(default=None, description="Garage: ёмкость ноды.")


class CreateClusterRequest(BaseModel):
    name:       str             = Field(..., examples=["prod-ceph-01"])
    engine:     StorageEngine
    hosts:      list[HostIn]   = Field(..., min_length=1)
    extra_vars: dict[str, Any] = Field(default_factory=dict)


class ScaleRequest(BaseModel):
    """Только новые ноды для добавления."""
    new_hosts: list[HostIn] = Field(..., min_length=1)


# ── POST /clusters ────────────────────────────────────────────────────────────

@router.post("", status_code=202, response_model=JobAcceptedResponse)
async def create_cluster(body: CreateClusterRequest):
    hosts_payload = [h.model_dump() for h in body.hosts]
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
    if doc["status"] != ClusterStatus.ready.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CLUSTER_NOT_READY",
                "message": f"Масштабирование возможно только в статусе ready, сейчас: {doc['status']}",
            },
        )

    from app.services.host_store import list_hosts
    existing_hosts = await list_hosts(cluster_id=cluster_id)

    new_hosts_payload = [h.model_dump() for h in body.new_hosts]
    existing_ips = {h["ip"] for h in existing_hosts}
    duplicates = [h["ip"] for h in new_hosts_payload if h["ip"] in existing_ips]
    if duplicates:
        raise HTTPException(
            status_code=409,
            detail={"code": "HOST_ALREADY_IN_CLUSTER", "message": f"Хосты уже в кластере: {', '.join(duplicates)}"},
        )

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
        raise HTTPException(status_code=404, detail={"code": "PLAYBOOK_NOT_FOUND", "message": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "ERROR", "message": str(e)})

    return {
        "job_id":     job_id,
        "cluster_id": cluster_id,
        "status":     "pending",
        "playbook":   f"scale_{doc['engine']}.yml",
        "message":    "Масштабирование запущено",
    }


# ── POST /clusters/{cluster_id}/retry ────────────────────────────────────────

@router.post("/{cluster_id}/retry", status_code=202)
async def retry_cluster(cluster_id: str):
    """
    Повторяет последнюю упавшую операцию кластера (deploy / scale / teardown).
    Доступно только если кластер в статусе failed.
    Определяет тип операции по последней failed-задаче.
    """
    doc = await get_cluster(cluster_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"Кластер {cluster_id} не найден"},
        )
    if doc["status"] != ClusterStatus.failed.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CLUSTER_NOT_FAILED",
                "message": f"Повтор доступен только в статусе failed, сейчас: {doc['status']}",
            },
        )

    # Найти последнюю упавшую задачу чтобы определить тип операции
    last_job = await get_last_failed_job(cluster_id)
    if not last_job:
        raise HTTPException(
            status_code=404,
            detail={"code": "NO_FAILED_JOB", "message": "Не найдена упавшая задача для повтора"},
        )

    job_type = last_job.get("job_type", JobType.deploy.value)
    engine   = doc["engine"]

    from app.services.host_store import list_hosts
    hosts = await list_hosts(cluster_id=cluster_id)

    if not hosts:
        raise HTTPException(
            status_code=409,
            detail={"code": "NO_HOSTS", "message": "Нет хостов в инвентаре кластера"},
        )

    try:
        if job_type == JobType.deploy.value:
            # Повторный deploy — переиспользуем те же хосты и extra_vars
            _, job_id = await run_deploy_async(
                engine=engine,
                hosts=hosts,
                extra_vars=doc.get("extra_vars", {}),
                name=doc["name"],
                cluster_id=cluster_id,   # передаём существующий cluster_id
            )
            playbook = f"deploy_{engine}.yml"

        elif job_type == JobType.scale.value:
            # Повторный scale — берём все хосты, новые = те что добавлялись
            new_hosts = last_job.get("extra_vars", {}).get("new_nodes_ips", [])
            new_hosts_docs = [h for h in hosts if h["ip"] in new_hosts] if new_hosts else []
            job_id = await run_scale_async(
                cluster_id=cluster_id,
                engine=engine,
                hosts=hosts,
                new_hosts=new_hosts_docs or hosts,
                extra_vars=doc.get("extra_vars", {}),
            )
            playbook = f"scale_{engine}.yml"

        elif job_type == JobType.teardown.value:
            # Повторный teardown
            job_id = await run_teardown_async(
                cluster_id=cluster_id,
                engine=engine,
                hosts=hosts,
                extra_vars=doc.get("extra_vars", {}),
            )
            playbook = f"teardown_{engine}.yml"

        else:
            raise HTTPException(
                status_code=422,
                detail={"code": "UNKNOWN_JOB_TYPE", "message": f"Неизвестный тип задачи: {job_type}"},
            )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "PLAYBOOK_NOT_FOUND", "message": str(e)})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "ERROR", "message": str(e)})

    return {
        "job_id":     job_id,
        "cluster_id": cluster_id,
        "status":     "pending",
        "playbook":   playbook,
        "job_type":   job_type,
        "message":    f"Повтор операции {job_type} запущен",
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
