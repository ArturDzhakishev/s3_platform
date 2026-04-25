from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    ANSIBLE_PLAYBOOKS_DIR: str = "./ansible/"
    ANSIBLE_RUNNER_BASE_DIR: str = "/tmp/ansible-runner"

    ANSIBLE_INVENTORY_DEFAULT: str | None = None
    ANSIBLE_INVENTORY_CEPH:       str | None = None   # ./ansible/ceph/hosts.ini
    ANSIBLE_INVENTORY_SEAWEEDFS:  str | None = None   # ./ansible/seaweedfs/hosts.ini
    ANSIBLE_INVENTORY_GARAGE:     str | None = None   # ./ansible/garage/hosts.ini

    # При добавлении БД — раскомментировать:
    # DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/s3platform"

    # При добавлении Celery — раскомментировать:
    # REDIS_URL: str = "redis://localhost:6379/0"

    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    def inventory_for(self, engine: str) -> str | None:
        """Возвращает путь к inventory-файлу для движка, либо default, либо None."""
        per_engine = {
            "ceph":      self.ANSIBLE_INVENTORY_CEPH,
            "seaweedfs": self.ANSIBLE_INVENTORY_SEAWEEDFS,
            "garage":    self.ANSIBLE_INVENTORY_GARAGE,
        }
        return per_engine.get(engine) or self.ANSIBLE_INVENTORY_DEFAULT


@lru_cache
def get_settings() -> Settings:
    return Settings()
