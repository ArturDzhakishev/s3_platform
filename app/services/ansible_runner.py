"""
Ansible runner service — минимальная версия.

Стратегия inventory (приоритет сверху вниз):
  1. Файл из настроек движка  (ANSIBLE_INVENTORY_CEPH / _SEAWEEDFS / _GARAGE)
  2. ANSIBLE_INVENTORY_DEFAULT
  3. Динамический inventory, сгенерированный из hosts[] в запросе

Стратегия inventory (приоритет сверху вниз):
  1. Файл из настроек движка (ANSIBLE_INVENTORY_CEPH / _SEAWEEDFS / _GARAGE)
  2. ANSIBLE_INVENTORY_DEFAULT
  3. Динамический inventory, сгенерированный из hosts[] в запросе

Жизненный цикл задачи:
  POST /run
    → resolve_inventory()          — выбрать inventory
    → create_job() в MongoDB       — статус: pending
    → asyncio.create_task()        — 202 Accepted возвращается клиенту
        → set_running()            — статус: running
        → _run_playbook_sync()     — ansible-runner в thread pool
        → set_finished()           — статус: success | failed
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
from app.schemas.enums import JobStatus, JobType, StorageEngine
from app.services.job_store import create_job, set_finished, set_running


log = logging.getLogger(__name__)
settings = get_settings()


# ── Dynamic inventory builder ─────────────────────────────────────────────────

def build_inventory(hosts: list[dict]) -> dict:
    """
    Строит in-memory Ansible inventory из hosts[] запроса.

    Первый хост → группа master (MON/MGR для Ceph, master для SeaweedFS).
    Остальные   → группа workers (OSD / volume-серверы).
    Роль можно переопределить явно через поле role: "master" | "worker".

    Группы master/workers используются в плейбуках через:
      groups['master'][0], groups['workers'], hostvars[item]['ansible_host']
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


# ── Фоновая корутина ──────────────────────────────────────────────────────────

async def _background_run(
    job_id: str,
    playbook_path: str,
    inventory: str | dict,
    extra_vars: dict[str, Any],
) -> None:
    """
    Запускается внутри asyncio.create_task() — клиент её не ждёт.

    Обновляет статус Job в MongoDB на каждом шаге:
      pending → running → success | failed
    """
    await set_running(job_id)
    log.info("Job %s → running  playbook=%s  inventory=%s",
             job_id, Path(playbook_path).name,
             inventory if isinstance(inventory, str) else "dynamic")

    runner_dir = os.path.join(settings.ANSIBLE_RUNNER_BASE_DIR, job_id)
    loop = asyncio.get_running_loop()

    try:
        rc, stdout = await loop.run_in_executor(
            None,
            _run_playbook_sync,
            playbook_path,
            inventory,
            extra_vars,
            runner_dir,
        )
    except Exception as exc:
        log.exception("Job %s: ошибка runner", job_id)
        await set_finished(job_id, rc=1, log=str(exc))
        return

    await set_finished(job_id, rc=rc, log=stdout)
    log.info("Job %s → %s  rc=%d", job_id, "success" if rc == 0 else "failed", rc)

# ── Public async API ──────────────────────────────────────────────────────────

async def run_playbook_async(
    engine: str,
    job_type: str,
    hosts: list[dict],
    extra_vars: dict[str, Any],
) -> str:
    playbook_name = f"{job_type}_{engine}.yml"
    playbook_path = str(
        Path(settings.ANSIBLE_PLAYBOOKS_DIR, engine, playbook_name).resolve()
    )

    if not os.path.isfile(playbook_path):
        raise FileNotFoundError(
            f"Playbook не найден: {playbook_path}\n"
            f"Проверьте ANSIBLE_PLAYBOOKS_DIR={settings.ANSIBLE_PLAYBOOKS_DIR}"
        )

    inventory = resolve_inventory(engine, hosts)

    job_id = await create_job(
        engine=engine,
        job_type=job_type,
        playbook=playbook_name,
        hosts=hosts,
        extra_vars=extra_vars,
    )

    asyncio.create_task(
        _background_run(job_id, playbook_path, inventory, extra_vars),
        name=f"ansible-{job_id}",
    )

    log.info("Job %s создан: %s (%s)", job_id, playbook_name, engine)
    return job_id


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