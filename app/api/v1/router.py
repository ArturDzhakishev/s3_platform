from fastapi import APIRouter
from app.api.v1.endpoints.playbooks import router as playbooks_router

api_router = APIRouter()
api_router.include_router(playbooks_router)

# EXTEND: при добавлении БД и Celery подключить сюда:
# from app.api.v1.endpoints.hosts import router as hosts_router
# from app.api.v1.endpoints.clusters import router as clusters_router
# from app.api.v1.endpoints.jobs import router as jobs_router
# api_router.include_router(hosts_router)
# api_router.include_router(clusters_router)
# api_router.include_router(jobs_router)
