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
При deploy записывает данные в три коллекции MongoDB:

  hosts    ← upsert каждого хоста (ip уникален), статус → in_use
  clusters ← новый документ, статус deploying
  jobs     ← новый документ, cluster_id = cluster_id

После выполнения плейбука фоновая корутина (_bg) обновляет:
  jobs     ← status, return_code, log, finished_at
  clusters ← status (ready / failed), s3_endpoint, error_msg
  hosts    ← (при teardown) status → available, cluster_id → None
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

import ansible_runner

from app.core.config import get_settings
from app.schemas.enums import ClusterStatus, JobType
from app.services.cluster_store import (
    create_cluster, delete_cluster,
    set_cluster_ready, set_cluster_status,
)
from app.services.host_store import release_hosts, upsert_host
from app.services.job_store import create_job, set_finished, set_running

log = logging.getLogger(__name__)
settings = get_settings()


# ── Dynamic inventory builder ─────────────────────────────────────────────────

def build_inventory(hosts: list[dict]) -> dict:
    all_h: dict = {}
    masters: dict = {}
    workers: dict = {}
    for i, h in enumerate(hosts):
        ip = h["ip"]
        entry: dict = {"ansible_host": ip, "ansible_user": h["ssh_user"], "ansible_port": h["ssh_port"]}
        if h.get("ssh_private_key_path"):
            entry["ansible_ssh_private_key_file"] = h["ssh_private_key_path"]
        all_h[ip] = entry
        role = h.get("role", "master" if i == 0 else "worker")
        (masters if role == "master" else workers)[ip] = {}
    return {"all": {"hosts": all_h, "children": {"master": {"hosts": masters}, "workers": {"hosts": workers}}}}

def _s3_endpoint(engine: str, hosts: list[dict]) -> str | None:
    master_ip = next(
        (h["ip"] for h in hosts if h.get("role") == "master"),
        hosts[0]["ip"] if hosts else None,
    )
    if not master_ip:
        return None
    ports = {"ceph": 7480, "seaweedfs": 8333, "garage": 3900}
    port = ports.get(engine, 80)
    return f"http://{master_ip}:{port}"

# ── Sync runner (thread pool) ─────────────────────────────────────────────────

def _run_sync(playbook_path: str, inventory: str | dict, extra_vars: dict, runner_dir: str) -> tuple[int, str]:
    Path(runner_dir).mkdir(parents=True, exist_ok=True)
    r = ansible_runner.run(
        private_data_dir=runner_dir,
        playbook=str(Path(playbook_path).resolve()),
        inventory=inventory,
        extravars=extra_vars,
        quiet=False,
    )
    return r.rc, (r.stdout.read() if r.stdout else "")


def _playbook_path(engine: str, job_type: str) -> str:
    name = f"{job_type}_{engine}.yml"
    path = str(Path(settings.ANSIBLE_PLAYBOOKS_DIR, engine, name).resolve())
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Playbook не найден: {path}")
    return path


# ── Deploy ────────────────────────────────────────────────────────────────────

async def run_deploy_async(
    engine:     str,
    hosts:      list[dict],
    extra_vars: dict[str, Any],
    name:       str = "",
) -> tuple[str, str]:
    """
    Сохранить hosts / cluster / job в MongoDB, запустить деплой в фоне.
    Возвращает (cluster_id, job_id).
    """
    pb_path   = _playbook_path(engine, "deploy")
    pb_name   = f"deploy_{engine}.yml"
    cluster_id = str(uuid.uuid4())
    job_id     = str(uuid.uuid4())

    # ── 1. hosts ──────────────────────────────────────────────────────────────
    host_ids: list[str] = []
    for h in hosts:
        hid = await upsert_host(
            ip=h["ip"],
            label=h.get("label", h["ip"]),
            ssh_user=h["ssh_user"],
            ssh_port=h["ssh_port"],
            ssh_private_key_path=h.get("ssh_private_key_path"),
            role=h.get("role", "worker"),
            cluster_id=cluster_id,
        )
        host_ids.append(hid)

    # ── 2. cluster ────────────────────────────────────────────────────────────
    await create_cluster(
        cluster_id=cluster_id,
        name=name or f"{engine}-{cluster_id[:8]}",
        engine=engine,
        host_ids=host_ids,
        extra_vars=extra_vars,
        deploy_job_id=job_id,
    )

    # ── 3. job ────────────────────────────────────────────────────────────────
    await create_job(
        job_id=job_id,
        cluster_id=cluster_id,
        engine=engine,
        job_type=JobType.deploy.value,
        playbook=pb_name,
        extra_vars=extra_vars,
    )

    inventory = build_inventory(hosts)

    # ── 4. фон ───────────────────────────────────────────────────────────────
    async def _bg() -> None:
        await set_running(job_id)
        log.info("Deploy %s → running  cluster=%s", job_id, cluster_id)
        runner_dir = os.path.join(settings.ANSIBLE_RUNNER_BASE_DIR, job_id)
        loop = asyncio.get_running_loop()
        try:
            rc, stdout = await loop.run_in_executor(None, _run_sync, pb_path, inventory, extra_vars, runner_dir)
        except Exception as exc:
            log.exception("Deploy %s: ошибка runner", job_id)
            await set_finished(job_id, rc=1, log=str(exc))
            await set_cluster_status(cluster_id, ClusterStatus.failed, error_msg=str(exc))
            return
        await set_finished(job_id, rc=rc, log=stdout)
        if rc == 0:
            await set_cluster_ready(cluster_id, s3_endpoint=_s3_endpoint(engine, hosts))
            log.info("Deploy %s → success", job_id)
        else:
            await set_cluster_status(cluster_id, ClusterStatus.failed, error_msg=f"rc={rc}")
            log.warning("Deploy %s → failed rc=%d", job_id, rc)

    asyncio.create_task(_bg(), name=f"deploy-{job_id}")
    return cluster_id, job_id

# ── Teardown ──────────────────────────────────────────────────────────────────

async def run_teardown_async(cluster_id: str, engine: str, hosts: list[dict], extra_vars: dict) -> str:
    pb_path = _playbook_path(engine, "teardown")
    pb_name = f"teardown_{engine}.yml"
    job_id  = str(uuid.uuid4())

    await create_job(
        job_id=job_id,
        cluster_id=cluster_id,
        engine=engine,
        job_type=JobType.teardown.value,
        playbook=pb_name,
        extra_vars=extra_vars,
    )
    inventory = build_inventory(hosts)

    async def _bg() -> None:
        await set_running(job_id)
        await set_cluster_status(cluster_id, ClusterStatus.deleting)
        runner_dir = os.path.join(settings.ANSIBLE_RUNNER_BASE_DIR, job_id)
        loop = asyncio.get_running_loop()
        try:
            rc, stdout = await loop.run_in_executor(None, _run_sync, pb_path, inventory, extra_vars, runner_dir)
        except Exception as exc:
            await set_finished(job_id, rc=1, log=str(exc))
            await set_cluster_status(cluster_id, ClusterStatus.failed, error_msg=str(exc))
            return
        await set_finished(job_id, rc=rc, log=stdout)
        if rc == 0:
            await release_hosts(cluster_id)
            await delete_cluster(cluster_id)
            log.info("Teardown %s → success, кластер %s удалён", job_id, cluster_id)
        else:
            await set_cluster_status(cluster_id, ClusterStatus.failed, error_msg=f"rc={rc}")

    asyncio.create_task(_bg(), name=f"teardown-{job_id}")
    return job_id


# ── Ping ──────────────────────────────────────────────────────────────────────

async def ping_host(ip: str, ssh_user: str, ssh_port: int, key_path: str | None) -> tuple[bool, float | None, str | None]:
    inv = {"all": {"hosts": {ip: {
        "ansible_host": ip, "ansible_user": ssh_user, "ansible_port": ssh_port,
        **({"ansible_ssh_private_key_file": key_path} if key_path else {}),
    }}}}
    runner_dir = os.path.join(settings.ANSIBLE_RUNNER_BASE_DIR, f"ping-{uuid.uuid4()}")
    Path(runner_dir).mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()

    def _ping():
        r = ansible_runner.run(private_data_dir=runner_dir, host_pattern="all",
                               module="ping", inventory=inv, quiet=True)
        return r.rc, r.stdout.read() if r.stdout else ""

    rc, stdout = await asyncio.get_running_loop().run_in_executor(None, _ping)
    ms = (time.monotonic() - t0) * 1000
    return (True, round(ms, 2), None) if rc == 0 else (False, None, stdout or "ping failed")
