from pydantic import BaseModel

class CephCreate(BaseModel):
    type: str
    master_ip: str
    nodes_ip: list[str]
    ssh_user: str
    ssh_key_path: str
    