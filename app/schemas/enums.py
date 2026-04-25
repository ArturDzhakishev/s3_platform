from enum import Enum


class StorageEngine(str, Enum):
    ceph = "ceph"
    seaweedfs = "seaweedfs"
    garage = "garage"


class JobStatus(str, Enum):
    running = "running"
    success = "success"
    failed = "failed"


class JobType(str, Enum):
    deploy = "deploy"
    scale = "scale"
    teardown = "teardown"


# При добавлении БД — добавить ClusterStatus, HostStatus сюда же.
