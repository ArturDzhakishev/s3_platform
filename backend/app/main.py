from fastapi import FastAPI
from app.api import ceph

app = FastAPI(
    title="S3-Compatible Storage Platform API",
    version="1.0.0",
    description="API для развёртывания и управления S3-совместимыми кластерами (Ceph, SeaweedFS, Garage).",
    docs_url="/docs",
    redoc_url="/redoc",
)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # в проде заменить на конкретный origin фронтенда
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

app.include_router(ceph.router, prefix="/api/v1")