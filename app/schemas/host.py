"""
Схемы коллекции hosts.

Документ в MongoDB:
{
    "host_id":              "uuid4",
    "label":                "node-master",
    "ip":                   "192.168.1.110",
    "ssh_user":             "ubuntu",
    "ssh_port":             22,
    "ssh_private_key_path": "/home/ubuntu/.ssh/id_rsa",
    "role":                 "master" | "worker",
    "status":               "available" | "in_use" | "unreachable",
    "cluster_id":           "uuid4" | null,
    "created_at":           ISODate,
    "updated_at":           ISODate
}
"""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.enums import HostStatus


class HostIn(BaseModel):
    """Хост из тела запроса POST /run."""
    label:               str         = Field(...,  examples=["node-master"])
    ip:                  str         = Field(...,  examples=["192.168.1.110"])
    ssh_user:            str         = Field(...,  examples=["ubuntu"])
    ssh_port:            int         = Field(22,   ge=1, le=65535)
    ssh_private_key_path: str | None = Field(None, examples=["/home/ubuntu/.ssh/id_rsa"])
    role:                str         = Field("worker", examples=["master", "worker"])


class HostDocument(BaseModel):
    """Полный документ из коллекции hosts."""
    host_id:              str
    label:                str
    ip:                   str
    ssh_user:             str
    ssh_port:             int
    ssh_private_key_path: str | None
    role:                 str
    status:               HostStatus
    cluster_id:           str | None
    created_at:           datetime
    updated_at:           datetime


class HostResponse(BaseModel):
    """Ответ API — без приватного ключа."""
    host_id:    str
    label:      str
    ip:         str
    ssh_user:   str
    ssh_port:   int
    role:       str
    status:     HostStatus
    cluster_id: str | None
    created_at: datetime
    updated_at: datetime
