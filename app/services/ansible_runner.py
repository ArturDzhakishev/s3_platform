"""
Ansible runner service — минимальная версия.

Стратегия inventory (приоритет сверху вниз):
  1. Файл из настроек движка  (ANSIBLE_INVENTORY_CEPH / _SEAWEEDFS / _GARAGE)
  2. ANSIBLE_INVENTORY_DEFAULT
  3. Динамический inventory, сгенерированный из hosts[] в запросе

Точки расширения отмечены комментариями «# EXTEND:».
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import ansible_runner

from app.core.config import get_settings

log = logging.getLogger(__name__)
settings = get_settings()


# ── Dynamic inventory builder ─────────────────────────────────────────────────

def build_inventory(hosts: list[dict]) -> dict:
    """
    Строит in-memory inventory когда статический hosts.ini не задан.

    hosts — список dict: ip, ssh_user, ssh_port, role?, ssh_key_path?
    Первый хост → master, остальные → workers (если role не указана явно).

    Группы master/workers и поле ansible_host обязательны для плейбуков,
    которые используют groups['master'], groups['workers'] и
    hostvars[item]['ansible_host'].
    """
    all_hosts: dict = {}
    master_hosts: dict = {}
    worker_hosts: dict = {}

    for i, h in enumerate(hosts):
        ip = h["ip"]
        entry: dict = {
            "ansible_host": ip,
            "ansible_user": h["ssh_user"],
            "ansible_port": h["ssh_port"],
        }
        if h.get("ssh_key_path"):
            entry["ansible_ssh_private_key_file"] = h["ssh_key_path"]

        all_hosts[ip] = entry

        role = h.get("role", "master" if i == 0 else "worker")
        if role == "master":
            master_hosts[ip] = {}
        else:
            worker_hosts[ip] = {}

    return {
        "all": {
            "hosts": all_hosts,
            "children": {
                "master":  {"hosts": master_hosts},
                "workers": {"hosts": worker_hosts},
            },
        }
    }


# ── Inventory resolver ────────────────────────────────────────────────────────

def resolve_inventory(engine: str, hosts: list[dict]) -> str | dict:
    """
    Возвращает inventory для ansible-runner.run():
      - str  → абсолютный путь к hosts.ini  (статический файл)
      - dict → in-memory inventory           (динамический, из запроса)

    Приоритет:
      1. ANSIBLE_INVENTORY_<ENGINE> из .env
      2. ANSIBLE_INVENTORY_DEFAULT из .env
      3. Динамический inventory из hosts[]

    ansible-runner принимает оба типа в параметре inventory=.
    """
    static_path = settings.inventory_for(engine)

    if static_path:
        abs_path = str(Path(static_path).resolve())
        if not Path(abs_path).exists():
            raise FileNotFoundError(
                f"Inventory-файл не найден: {abs_path}\n"
                f"Проверьте ANSIBLE_INVENTORY_{engine.upper()} в .env"
            )
        log.info("Используется статический inventory: %s", abs_path)
        return abs_path

    if not hosts:
        raise ValueError(
            "Не задан ни статический inventory-файл (ANSIBLE_INVENTORY_*), "
            "ни список хостов (hosts[]) в запросе."
        )

    log.info("Используется динамический inventory (%d хостов)", len(hosts))
    return build_inventory(hosts)


# ── Core runner (sync, runs in thread pool) ───────────────────────────────────

def _run_playbook_sync(
    playbook_path: str,
    inventory: str | dict,
    extra_vars: dict[str, Any],
    runner_dir: str,
) -> tuple[int, str]:
    """
    Блокирующий запуск ansible-runner.

    playbook_path — абсолютный путь (избегаем разрешения относительно private_data_dir).
    inventory     — путь к файлу или in-memory dict.
    """
    Path(runner_dir).mkdir(parents=True, exist_ok=True)

    r = ansible_runner.run(
        private_data_dir=runner_dir,
        playbook=str(Path(playbook_path).resolve()),
        inventory=inventory,
        extravars=extra_vars,
        quiet=False,
    )
    stdout = r.stdout.read() if r.stdout else ""
    return r.rc, stdout


# ── Public async API ──────────────────────────────────────────────────────────

async def run_playbook(
    engine: str,
    job_type: str,
    hosts: list[dict],
    extra_vars: dict[str, Any],
) -> tuple[int, str, str]:
    """
    Запускает плейбук асинхронно (в thread pool).
    Возвращает (return_code, stdout_log, playbook_name).

    EXTEND: при добавлении Celery — заменить run_in_executor на task.delay().
    EXTEND: при добавлении БД — принимать job_id, обновлять Job.status.
    """
    playbook_name = f"{job_type}_{engine}.yml"
    playbook_path = str(Path(settings.ANSIBLE_PLAYBOOKS_DIR, engine, playbook_name).resolve())

    if not os.path.isfile(playbook_path):
        raise FileNotFoundError(
            f"Playbook не найден: {playbook_path}\n"
            f"Проверьте ANSIBLE_PLAYBOOKS_DIR={settings.ANSIBLE_PLAYBOOKS_DIR}"
        )

    inventory = resolve_inventory(engine, hosts)
    runner_dir = os.path.join(settings.ANSIBLE_RUNNER_BASE_DIR, str(uuid.uuid4()))

    log.info("Запуск %s | inventory: %s", playbook_name,
             inventory if isinstance(inventory, str) else "dynamic")

    loop = asyncio.get_running_loop()
    rc, stdout = await loop.run_in_executor(
        None,
        _run_playbook_sync,
        playbook_path,
        inventory,
        extra_vars,
        runner_dir,
    )

    log.info("Плейбук %s завершён rc=%d", playbook_name, rc)
    return rc, stdout, playbook_name


async def ping_host(
    ip: str,
    ssh_user: str,
    ssh_port: int,
    key_path: str | None,
) -> tuple[bool, float | None, str | None]:
    """
    Ansible ping одного хоста.
    EXTEND: при добавлении БД — принимать host_id, обновлять Host.status.
    """
    import time

    inventory = {
        "all": {
            "hosts": {
                ip: {
                    "ansible_host": ip,
                    "ansible_user": ssh_user,
                    "ansible_port": ssh_port,
                    **({"ansible_ssh_private_key_file": key_path} if key_path else {}),
                }
            }
        }
    }

    runner_dir = os.path.join(settings.ANSIBLE_RUNNER_BASE_DIR, f"ping-{uuid.uuid4()}")
    Path(runner_dir).mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()

    def _ping():
        r = ansible_runner.run(
            private_data_dir=runner_dir,
            host_pattern="all",
            module="ping",
            inventory=inventory,
            quiet=True,
        )
        return r.rc, r.stdout.read() if r.stdout else ""

    loop = asyncio.get_running_loop()
    rc, stdout = await loop.run_in_executor(None, _ping)
    elapsed_ms = (time.monotonic() - t0) * 1000

    if rc == 0:
        return True, round(elapsed_ms, 2), None
    return False, None, stdout or "ansible ping failed"