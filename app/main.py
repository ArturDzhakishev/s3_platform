"""
S3 Platform — MVP.

Запускает Ansible-плейбуки без БД и Celery.
Все точки расширения помечены комментарием «# EXTEND:».
"""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)
settings = get_settings()

# EXTEND: при добавлении БД добавить lifespan с create_all_tables / Alembic.
# from contextlib import asynccontextmanager
# @asynccontextmanager
# async def lifespan(app):
#     await create_all_tables()
#     yield
# app = FastAPI(..., lifespan=lifespan)

app = FastAPI(
    title="S3-Compatible Storage Platform API — MVP",
    version="0.1.0",
    description=(
        "Минимальная версия: запуск Ansible-плейбуков через REST.\n\n"
        "Следующие шаги: добавить БД (Host/Cluster/Job), Celery, Redis."
    ),
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": str(exc)},
    )
