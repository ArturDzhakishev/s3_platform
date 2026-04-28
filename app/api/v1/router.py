from fastapi import APIRouter
from app.api.v1.endpoints.clusters import router as clusters_router
from app.api.v1.endpoints.playbooks import router as tools_router

api_router = APIRouter()
api_router.include_router(clusters_router)
api_router.include_router(tools_router)