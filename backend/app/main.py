from fastapi import FastAPI
from app.api import ceph

app = FastAPI(title="S3 Platform")

app.include_router(ceph.router)