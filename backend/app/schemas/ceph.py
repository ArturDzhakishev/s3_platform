from pydantic import BaseModel

class CephCreate(BaseModel):
    type: str
    master_ip: str
    nodes_ip: list[str]