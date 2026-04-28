"""
Pydantic-схемы для документа Cluster в MongoDB.

Структура документа в коллекции clusters:
{
    "cluster_id": "uuid4",
    "name":       "prod-ceph-01",
    "engine":     "ceph" | "seaweedfs" | "garage",
    "status":     "deploying" | "ready" | "scaling" | "deleting" | "failed",
    "hosts": [
        {"ip": "...", "ssh_user": "...", "ssh_port": 22,
         "ssh_private_key_path": "...", "role": "master"|"worker",
         "status": "in_use"}
    ],
    "extra_vars":  {...},
    "created_at":  datetime,
    "updated_at":  datetime
}
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.enums import ClusterStatus, StorageEngine


class ClusterResponse(BaseModel):
    cluster_id:    str
    name:          str
    engine:        StorageEngine
    status:        ClusterStatus
    host_ids:      list[str]
    node_count:    int
    extra_vars:    dict[str, Any]
    s3_endpoint:   str | None
    error_msg:     str | None
    deploy_job_id: str
    created_at:    datetime
    updated_at:    datetime
