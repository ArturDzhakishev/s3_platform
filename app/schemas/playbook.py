"""
Pydantic schemas for the playbook execution API.

Намеренно плоские — без моделей Cluster/Host/Job из БД.
При добавлении БД эти схемы станут входными DTO,
а ответы будут формироваться из ORM-моделей.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from app.schemas.enums import JobStatus, JobType, StorageEngine


class HostEntry(BaseModel):
    """Один хост для инвентаря Ansible."""

    ip: str = Field(..., examples=["192.168.1.10"])
    ssh_user: str = Field(..., examples=["ubuntu"])
    ssh_port: int = Field(default=22, ge=1, le=65535)
    # Путь к ключу на диске ИЛИ PEM-содержимое.
    # При добавлении шифрования — перенести в HostModel БД.
    ssh_private_key_path: str | None = Field(
        default=None,
        description="Абсолютный путь к приватному SSH-ключу на сервере платформы.",
    )


class RunPlaybookRequest(BaseModel):
    """Запрос на запуск произвольного плейбука."""

    engine: StorageEngine
    job_type: JobType
    hosts: list[HostEntry] = Field(default_factory=list)
    extra_vars: dict[str, Any] = Field(
        default_factory=dict,
        examples=[{"ceph_osd_pool_default_size": 3}],
    )


class PlaybookResult(BaseModel):
    """Синхронный результат выполнения плейбука."""

    job_type: JobType
    engine: StorageEngine
    status: JobStatus
    playbook: str
    log: str
    return_code: int

    # Заглушки для будущих полей БД:
    # cluster_id: str | None = None
    # job_id: str | None = None
