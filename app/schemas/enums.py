from enum import Enum


class StorageEngine(str, Enum):
    ceph = "ceph"
    seaweedfs = "seaweedfs"
    garage = "garage"


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class JobType(str, Enum):
    deploy = "deploy"
    scale = "scale"
    teardown = "teardown"


class ClusterStatus(str, Enum):
    deploying = "deploying"
    ready = "ready"
    scaling = "scaling"
    deleting = "deleting"
    failed = "failed"


class HostStatus(str, Enum):
    available = "available"
    in_use = "in_use"
    unreachable = "unreachable"