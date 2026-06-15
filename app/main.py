"""
S3 Platform — MVP.

Изменения относительно MVP:
  - lifespan: подключение к MongoDB при старте, индексы, закрытие при остановке
  - POST /run возвращает 202 + job_id вместо синхронного ответа

"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.mongo import close_client, create_indexes, get_client

logging.basicConfig(level=logging.INFO)
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Старт: подключиться к MongoDB и создать индексы
    client = get_client()
    await create_indexes()
    logging.info("MongoDB connected: %s / %s", settings.MONGODB_URL, settings.MONGODB_DB)
    yield
    # Остановка: закрыть соединение
    await close_client()
    logging.info("MongoDB disconnected")


app = FastAPI(
    title="S3-platform",
    version="0.1.0",
    description=(
        "Асинхронный запуск Ansible-плейбуков.\n\n"
        "POST /run → 202 + job_id. "
        "Статус: GET /jobs/{job_id}."
    ),
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": str(exc)},
    )
