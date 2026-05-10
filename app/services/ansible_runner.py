"""
Ansible runner service.

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
import functools
import tempfile
from datetime import datetime, timezone
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


# ── SSH key helper ────────────────────────────────────────────────────────────

def _write_key_files(hosts: list[dict], keys_dir: str) -> list[dict]:
    """
    Если хост передал PEM-содержимое (ssh_private_key) вместо пути,
    записать его в keys_dir/key_{i} с правами 0600.

    keys_dir должен существовать всё время работы плейбука —
    используй постоянную директорию (runner_dir/keys/), а не TemporaryDirectory.
    """
    Path(keys_dir).mkdir(parents=True, exist_ok=True)
    result = []
    for i, h in enumerate(hosts):
        h = dict(h)
        pem = h.get("ssh_private_key")
        has_path = bool(h.get("ssh_private_key_path"))
        if pem and not has_path:
            # Файл без расширения — Ansible не требует расширения
            key_path = os.path.join(keys_dir, f"key_{i}")
            with open(key_path, "w") as f:
                f.write(pem)
            os.chmod(key_path, 0o600)
            h["ssh_private_key_path"] = key_path
            log.debug("SSH key written: %s", key_path)
        result.append(h)
    return result

# ── Inventory ─────────────────────────────────────────────────────────────────

def build_inventory(
    hosts:      list[dict],
    engine:     str = "",
    runner_dir: str = "",
    new_ips:    set[str] | None = None,   # IP новых нод для группы new_workers
) -> str:
    """
    Генерирует hosts.ini и записывает в runner_dir/inventory/hosts.ini.
    Возвращает путь к файлу.

    Группы по движкам:
      ceph      — [master], [workers], [new_workers]
      seaweedfs — [seaweedfs], [s3], [loadbalancer]
      garage    — [garage], [new_nodes]
    """
    master_h  = next((h for h in hosts if h.get("role") == "master"), hosts[0])
    master_ip = master_h["ip"]
    worker_hs = [h for h in hosts if h["ip"] != master_ip]
    new_ips   = new_ips or set()

    def host_line(name: str, ip: str) -> str:
        return f"{name} ansible_host={ip}"

    if engine == "ceph":
        master_name = master_h.get("label", "node-master")
        lines = ["[master]", host_line(master_name, master_ip), "[workers]"]
        for h in worker_hs:
            lines.append(host_line(h.get("label", h["ip"]), h["ip"]))
        # new_workers — только добавляемые ноды, для scale_ceph.yml
        lines.append("[new_workers]")
        new_worker_hs = [h for h in worker_hs if h["ip"] in new_ips]
        for h in new_worker_hs:
            lines.append(host_line(h.get("label", h["ip"]), h["ip"]))
        groups_ini = "\n".join(lines)

    elif engine == "seaweedfs":
        # Имя ноды — из label, стабильно между deploy и scale
        names = {h["ip"]: h.get("label", f"node{i}") for i, h in enumerate(hosts, start=1)}
        all_groups = ["seaweedfs", "s3", "loadbalancer"]
        # Построить маппинг группа → список хостов
        group_map: dict[str, list[dict]] = {g: [] for g in all_groups}
        
        for h in hosts:
            custom = h.get("groups", [])
            if custom:
                # Клиент явно указал группы
                for g in custom:
                    if g in group_map:
                        group_map[g].append(h)
            else:
                # Дефолт: все ноды в seaweedfs,
                # мастер в s3 и loadbalancer
                group_map["seaweedfs"].append(h)
                if h["ip"] == master_ip:
                    group_map["s3"].append(h)
                    group_map["loadbalancer"].append(h)

        # Гарантировать: нода в s3/loadbalancer всегда и в seaweedfs
        seaweedfs_ips = {h["ip"] for h in group_map["seaweedfs"]}
        for g in ("s3", "loadbalancer"):
            for h in group_map[g]:
                if h["ip"] not in seaweedfs_ips:
                    group_map["seaweedfs"].append(h)
                    seaweedfs_ips.add(h["ip"])

        lines = []
        for g in all_groups:
            lines.append(f"[{g}]")
            for h in group_map[g]:
                lines.append(host_line(names[h["ip"]], h["ip"]))
        groups_ini = "\n".join(lines)

    elif engine == "garage":
        # workers первыми, master последним — как в эталонном hosts.ini
        ordered = worker_hs + [master_h]
        # имя из label — стабильно между deploy и scale (не по индексу!)
        names = {h["ip"]: h.get("label", h["ip"]) for h in ordered}
        lines = ["[garage]"]
        for h in ordered:
            lines.append(host_line(names[h["ip"]], h["ip"]))
        # [new_nodes] — только добавляемые ноды (для scale_garage.yml)
        # при deploy new_ips пустой — группа будет пустой, плейбук её проигнорирует
        lines.append("[new_nodes]")
        for h in ordered:
            if h["ip"] in new_ips:
                lines.append(host_line(names[h["ip"]], h["ip"]))
        groups_ini = "\n".join(lines)

    else:
        master_name = master_h.get("label", "node-master")
        lines = ["[master]", host_line(master_name, master_ip), "[workers]"]
        for h in worker_hs:
            lines.append(host_line(h.get("label", h["ip"]), h["ip"]))
        groups_ini = "\n".join(lines)

    first = hosts[0]
    vars_lines = [
        "[all:vars]",
        f"ansible_user={first['ssh_user']}",
        "ansible_python_interpreter=/usr/bin/python3",
    ]
    if first.get("ssh_private_key_path"):
        vars_lines.append(f"ansible_ssh_private_key_file={first['ssh_private_key_path']}")

    ini = groups_ini + "\n" + "\n".join(vars_lines) + "\n"

    inv_dir = Path(runner_dir) / "inventory"
    inv_dir.mkdir(parents=True, exist_ok=True)
    inv_path = inv_dir / "hosts.ini"
    inv_path.write_text(ini)
    log.debug("Inventory:\n%s", ini)
    return str(inv_path)


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

def _run_sync(
    playbook_path: str,
    inventory:     str | dict,
    runner_dir:    str,
    extra_vars:    dict | None = None,
) -> tuple[int, str]:
    """
    Запускает плейбук синхронно (вызывается из thread pool).
    extra_vars передаются через extravars ansible-runner.
    """
    Path(runner_dir).mkdir(parents=True, exist_ok=True)
    r = ansible_runner.run(
        private_data_dir=runner_dir,
        playbook=str(Path(playbook_path).resolve()),
        inventory=inventory,
        extravars=extra_vars or {},
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

    if engine == "garage":
        extra_vars = {
            **extra_vars,
            "garage_nodes_config": {
                h.get("label", h["ip"]): {
                    "zone":     h.get("zone")     or "default",
                    "capacity": h.get("capacity") or "1G",
                }
                for h in hosts
            },
        }

    # 1. Upsert хостов в MongoDB
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
            zone=h.get("zone"),
            capacity=h.get("capacity"),
        )
        host_ids.append(hid)

    # 2. Создать документ кластера
    await create_cluster(
        cluster_id=cluster_id,
        name=name or f"{engine}-{cluster_id[:8]}",
        engine=engine,
        host_ids=host_ids,
        extra_vars=extra_vars,
        deploy_job_id=job_id,
    )

    # 3. Создать документ job
    await create_job(
        job_id=job_id,
        cluster_id=cluster_id,
        engine=engine,
        job_type=JobType.deploy.value,
        playbook=pb_name,
        extra_vars=extra_vars,
    )

    # 4. Запустить плейбук в фоне
    async def _bg() -> None:
        await set_running(job_id)
        log.info("Deploy %s → running  cluster=%s", job_id, cluster_id)
        # keys_dir внутри runner_dir — живёт всё время работы плейбука
        runner_dir = os.path.join(settings.ANSIBLE_RUNNER_BASE_DIR, cluster_id, job_id)
        keys_dir   = os.path.join(settings.ANSIBLE_RUNNER_BASE_DIR, cluster_id, "keys")
        prepared   = _write_key_files(hosts, keys_dir)
        inventory  = build_inventory(prepared, engine=engine, runner_dir=runner_dir)
        loop = asyncio.get_running_loop()
        try:
            rc, stdout = await loop.run_in_executor(
                None,
                functools.partial(_run_sync, pb_path, inventory, runner_dir, extra_vars),
            )
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

    async def _bg() -> None:
        await set_running(job_id)
        await set_cluster_status(cluster_id, ClusterStatus.deleting)
        runner_dir = os.path.join(settings.ANSIBLE_RUNNER_BASE_DIR, cluster_id, job_id)
        keys_dir   = os.path.join(settings.ANSIBLE_RUNNER_BASE_DIR, cluster_id, "keys")
        prepared   = _write_key_files(hosts, keys_dir)
        inventory  = build_inventory(prepared, engine=engine, runner_dir=runner_dir)
        loop = asyncio.get_running_loop()
        try:
            rc, stdout = await loop.run_in_executor(
                None,
                functools.partial(_run_sync, pb_path, inventory, runner_dir, extra_vars),
            )
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

# ── Scale ─────────────────────────────────────────────────────────────────────

async def run_scale_async(
    cluster_id: str,
    engine:     str,
    hosts:      list[dict],        # все ноды (старые + новые)
    new_hosts:  list[dict],        # только новые — для передачи в extra_vars
    extra_vars: dict,
) -> str:
    """
    Масштабирование — запуск scale_{engine}.yml с обновлённым инвентарём.

    Новые ноды передаются в extra_vars как new_nodes_ips (список IP).
    Плейбук использует эту переменную чтобы ограничить деструктивные
    задачи (зачистка диска, инициализация OSD) только новыми нодами:

        when: inventory_hostname in new_nodes_ips

    Существующие ноды Ansible проверит но диски не тронет.
    """
    pb_path = _playbook_path(engine, "scale")
    pb_name = f"scale_{engine}.yml"
    job_id  = str(uuid.uuid4())

    # IP новых нод — передадим в плейбук
    new_nodes_ips = [h["ip"] for h in new_hosts]

    # Объединить extra_vars с информацией о новых нодах
    scale_vars = {
        **extra_vars,
        "new_nodes_ips": new_nodes_ips,   # используется в when: условиях плейбука
        "is_scale":      True,             # флаг для плейбука: режим масштабирования
    }

    # Garage: пересобрать garage_nodes_config со всеми нодами (старые + новые)
    if engine == "garage":
        scale_vars["garage_nodes_config"] = {
            h.get("label", h["ip"]): {
                "zone":     h.get("zone")     or "default",
                "capacity": h.get("capacity") or "1G",
            }
            for h in hosts
        }

    # Upsert всех нод (новые создадутся, старые обновятся)
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
            zone=h.get("zone"),
            capacity=h.get("capacity"),
        )
        host_ids.append(hid)

    # Обновить host_ids и node_count в документе кластера
    from app.db.mongo import get_clusters_collection
    await get_clusters_collection().update_one(
        {"cluster_id": cluster_id},
        {"$set": {
            "host_ids":   host_ids,
            "node_count": len(host_ids),
            "status":     ClusterStatus.scaling.value,
            "updated_at": datetime.now(timezone.utc),
        }},
    )

    await create_job(
        job_id=job_id,
        cluster_id=cluster_id,
        engine=engine,
        job_type=JobType.scale.value,
        playbook=pb_name,
        extra_vars=scale_vars,
    )

    async def _bg() -> None:
        await set_running(job_id)
        log.info("Scale %s → running  cluster=%s new_nodes=%s", job_id, cluster_id, new_nodes_ips)
        runner_dir = os.path.join(settings.ANSIBLE_RUNNER_BASE_DIR, job_id)
        inventory  = build_inventory(hosts, engine=engine, runner_dir=runner_dir, new_ips=set(new_nodes_ips))
        loop = asyncio.get_running_loop()
        try:
            rc, stdout = await loop.run_in_executor(
                None,
                functools.partial(_run_sync, pb_path, inventory, runner_dir, scale_vars),
            )
        except Exception as exc:
            log.exception("Scale %s: ошибка runner", job_id)
            await set_finished(job_id, rc=1, log=str(exc))
            await set_cluster_status(cluster_id, ClusterStatus.failed, error_msg=str(exc))
            return
        await set_finished(job_id, rc=rc, log=stdout)
        if rc == 0:
            await set_cluster_ready(cluster_id, s3_endpoint=_s3_endpoint(engine, hosts))
            log.info("Scale %s → success", job_id)
        else:
            await set_cluster_status(cluster_id, ClusterStatus.failed, error_msg=f"scale rc={rc}")
            log.warning("Scale %s → failed rc=%d", job_id, rc)

    asyncio.create_task(_bg(), name=f"scale-{job_id}")
    return job_id

# ── Ping ──────────────────────────────────────────────────────────────────────

async def ping_host(
    ip: str, ssh_user: str, ssh_port: int, key_path: str | None
) -> tuple[bool, float | None, str | None]:
    inv = {"all": {"hosts": {ip: {
        "ansible_host": ip,
        "ansible_user": ssh_user,
        "ansible_port": ssh_port,
        **({"ansible_ssh_private_key_file": key_path} if key_path else {}),
    }}}}
    runner_dir = os.path.join(settings.ANSIBLE_RUNNER_BASE_DIR, f"ping-{uuid.uuid4()}")
    Path(runner_dir).mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()

    def _ping():
        r = ansible_runner.run(
            private_data_dir=runner_dir,
            host_pattern="all",
            module="ping",
            inventory=inv,
            quiet=True,
        )
        return r.rc, r.stdout.read() if r.stdout else ""

    rc, stdout = await asyncio.get_running_loop().run_in_executor(None, _ping)
    ms = (time.monotonic() - t0) * 1000
    return (True, round(ms, 2), None) if rc == 0 else (False, None, stdout or "ping failed")