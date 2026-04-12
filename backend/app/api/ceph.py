from fastapi import APIRouter, BackgroundTasks
from app.schemas.ceph import CephCreate
from app.tasks.deploy_tasks import deploy_ceph_task

router = APIRouter(prefix="/ceph", tags=["Ceph"])

@router.post("/deploy")
def deploy_cluster(data: CephCreate, bg: BackgroundTasks):
    cluster_id = 1

    bg.add_task(deploy_ceph_task, cluster_id, data)

    return {"cluster_id": cluster_id, "status": "creating"}

# @router.get("/{cluster_id}")
# def get_cluster(cluster_id: int):
#     return {"id": cluster_id, "status": "running"}