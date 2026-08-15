from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, or_
from sqlalchemy.orm import Session

from app.config import get_settings
from app.events import bus
from app.models import (
    AgentCommand,
    Container,
    MetricSample,
    PackageUpdate,
    Remote,
    Setting,
    Task,
    User,
    utcnow,
)
from app.schemas import (
    ContainerOut,
    DashboardOut,
    MetricPoint,
    PackageUpdateOut,
    RemoteOut,
    SearchHit,
    TaskOut,
)
from app.security import hash_password, hash_token, new_token, verify_password


def ensure_bootstrap(db: Session) -> None:
    settings = get_settings()
    if db.query(User).count() == 0:
        if not settings.admin_password:
            raise RuntimeError("ADMIN_PASSWORD must be set on first start")
        db.add(
            User(
                id=str(uuid.uuid4()),
                username=settings.admin_user,
                password_hash=hash_password(settings.admin_password),
            )
        )
    token_row = db.get(Setting, "enrollment_token_hash")
    if token_row is None:
        token = settings.enrollment_token or new_token(24)
        db.add(Setting(key="enrollment_token_hash", value=hash_token(token)))
        db.add(Setting(key="enrollment_token_plain", value=token))
    db.commit()


def get_enrollment_token(db: Session) -> str:
    row = db.get(Setting, "enrollment_token_plain")
    return row.value if row else ""


def rotate_enrollment_token(db: Session) -> str:
    token = new_token(24)
    for key, value in (
        ("enrollment_token_hash", hash_token(token)),
        ("enrollment_token_plain", token),
    ):
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=value))
        else:
            row.value = value
    db.commit()
    return token


def create_remote(db: Session, name: str, notes: str = "", tags: str = "") -> tuple[Remote, str]:
    token = new_token(32)
    remote = Remote(
        id=str(uuid.uuid4()),
        name=name,
        hostname="",
        agent_id=f"agt_{new_token(12)}",
        token_hash=hash_token(token),
        notes=notes,
        tags=tags,
        status="pending",
    )
    db.add(remote)
    db.commit()
    db.refresh(remote)
    return remote, token


def enroll_agent(db: Session, enrollment_token: str, hostname: str, name: str | None) -> tuple[Remote, str]:
    expected = db.get(Setting, "enrollment_token_hash")
    if expected is None or hash_token(enrollment_token) != expected.value:
        raise ValueError("Invalid enrollment token")

    existing = db.query(Remote).filter(Remote.hostname == hostname).one_or_none()
    token = new_token(32)
    if existing and existing.status == "pending" and not existing.last_seen:
        existing.token_hash = hash_token(token)
        existing.hostname = hostname
        existing.name = name or existing.name or hostname
        db.commit()
        db.refresh(existing)
        return existing, token

    if existing and existing.last_seen:
        existing.token_hash = hash_token(token)
        existing.hostname = hostname
        if name:
            existing.name = name
        db.commit()
        db.refresh(existing)
        return existing, token

    remote = Remote(
        id=str(uuid.uuid4()),
        name=name or hostname,
        hostname=hostname,
        agent_id=f"agt_{new_token(12)}",
        token_hash=hash_token(token),
        status="pending",
    )
    db.add(remote)
    db.commit()
    db.refresh(remote)
    return remote, token


def _mem_percent(remote: Remote) -> float:
    if remote.mem_total <= 0:
        return 0.0
    return round((remote.mem_used / remote.mem_total) * 100, 1)


def _disk_percent(remote: Remote) -> float:
    if remote.disk_total <= 0:
        return 0.0
    return round((remote.disk_used / remote.disk_total) * 100, 1)


def compute_status(remote: Remote) -> str:
    settings = get_settings()
    if remote.last_seen is None:
        return "pending"
    last_seen = remote.last_seen
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    if utcnow() - last_seen > timedelta(seconds=settings.offline_after_seconds):
        return "offline"
    if (
        remote.cpu_percent >= settings.degraded_cpu_percent
        or _mem_percent(remote) >= settings.degraded_mem_percent
        or (remote.temperature_c is not None and remote.temperature_c >= settings.degraded_temp_c)
        or remote.under_voltage
        or remote.thermal_throttled
    ):
        return "degraded"
    return "online"


def refresh_remote_status(db: Session, remote: Remote | None = None) -> None:
    remotes = [remote] if remote is not None else db.query(Remote).all()
    for item in remotes:
        item.status = compute_status(item)
    db.commit()


def _container_counts(db: Session, remote_id: str) -> tuple[int, int]:
    total = db.query(func.count(Container.id)).filter(Container.remote_id == remote_id).scalar() or 0
    running = (
        db.query(func.count(Container.id))
        .filter(Container.remote_id == remote_id, Container.state == "running")
        .scalar()
        or 0
    )
    return int(running), int(total)


def _update_counts(db: Session, remote_id: str) -> tuple[int, int]:
    total = (
        db.query(func.count(PackageUpdate.id)).filter(PackageUpdate.remote_id == remote_id).scalar()
        or 0
    )
    security = (
        db.query(func.count(PackageUpdate.id))
        .filter(PackageUpdate.remote_id == remote_id, PackageUpdate.is_security.is_(True))
        .scalar()
        or 0
    )
    return int(total), int(security)


def remote_to_out(db: Session, remote: Remote) -> RemoteOut:
    running, total = _container_counts(db, remote.id)
    updates, security = _update_counts(db, remote.id)
    data = RemoteOut.model_validate(remote)
    return data.model_copy(
        update={
            "container_running": running,
            "container_total": total,
            "updates_available": updates,
            "security_updates": security,
        }
    )


def container_to_out(container: Container, remote_name: str = "") -> ContainerOut:
    try:
        ports = json.loads(container.ports or "[]")
    except json.JSONDecodeError:
        ports = []
    return ContainerOut(
        id=container.id,
        remote_id=container.remote_id,
        remote_name=remote_name,
        docker_id=container.docker_id,
        name=container.name,
        image=container.image,
        status=container.status,
        state=container.state,
        health=container.health,
        cpu_percent=container.cpu_percent,
        mem_usage=container.mem_usage,
        mem_limit=container.mem_limit,
        ports=ports if isinstance(ports, list) else [],
        created=container.created,
        compose_project=container.compose_project,
    )


def task_to_out(task: Task, remote_name: str = "") -> TaskOut:
    return TaskOut(
        id=task.id,
        remote_id=task.remote_id,
        remote_name=remote_name,
        type=task.type,
        target=task.target,
        status=task.status,
        requested_by=task.requested_by,
        log=task.log,
        error=task.error,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )


def apply_heartbeat(db: Session, remote: Remote, payload: dict[str, Any]) -> Remote:
    settings = get_settings()
    metrics = payload.get("metrics") or {}
    identity = payload.get("identity") or {}

    remote.last_seen = utcnow()
    remote.hostname = identity.get("hostname") or remote.hostname
    remote.os_pretty = identity.get("os_pretty") or remote.os_pretty
    remote.kernel = identity.get("kernel") or remote.kernel
    remote.arch = identity.get("arch") or remote.arch
    remote.model = identity.get("model") or remote.model
    remote.cpu_percent = float(metrics.get("cpu_percent") or 0)
    remote.mem_used = int(metrics.get("mem_used") or 0)
    remote.mem_total = int(metrics.get("mem_total") or 0)
    remote.disk_used = int(metrics.get("disk_used") or 0)
    remote.disk_total = int(metrics.get("disk_total") or 0)
    remote.load_1 = float(metrics.get("load_1") or 0)
    remote.load_5 = float(metrics.get("load_5") or 0)
    remote.load_15 = float(metrics.get("load_15") or 0)
    remote.temperature_c = metrics.get("temperature_c")
    remote.uptime_seconds = int(metrics.get("uptime_seconds") or 0)
    remote.net_rx_bytes = int(metrics.get("net_rx_bytes") or 0)
    remote.net_tx_bytes = int(metrics.get("net_tx_bytes") or 0)
    remote.cpu_count = int(metrics.get("cpu_count") or 0)
    remote.throttled = str(metrics.get("throttled") or "")
    remote.under_voltage = bool(metrics.get("under_voltage"))
    remote.thermal_throttled = bool(metrics.get("thermal_throttled"))
    remote.docker_available = bool(metrics.get("docker_available"))
    remote.status = compute_status(remote)

    db.add(
        MetricSample(
            remote_id=remote.id,
            cpu_percent=remote.cpu_percent,
            mem_percent=_mem_percent(remote),
            disk_percent=_disk_percent(remote),
            load_1=remote.load_1,
            temperature_c=remote.temperature_c,
        )
    )
    db.flush()
    keep_ids = [
        row.id
        for row in (
            db.query(MetricSample.id)
            .filter(MetricSample.remote_id == remote.id)
            .order_by(MetricSample.captured_at.desc())
            .limit(settings.metric_history_limit)
            .all()
        )
    ]
    if keep_ids:
        db.execute(
            delete(MetricSample).where(
                MetricSample.remote_id == remote.id, MetricSample.id.not_in(keep_ids)
            )
        )

    seen_ids: set[str] = set()
    for item in payload.get("containers") or []:
        docker_id = str(item.get("docker_id") or "")[:64]
        if not docker_id:
            continue
        seen_ids.add(docker_id)
        container = (
            db.query(Container)
            .filter(Container.remote_id == remote.id, Container.docker_id == docker_id)
            .one_or_none()
        )
        if container is None:
            container = Container(
                id=str(uuid.uuid4()),
                remote_id=remote.id,
                docker_id=docker_id,
            )
            db.add(container)
        container.name = str(item.get("name") or docker_id[:12])
        container.image = str(item.get("image") or "")
        container.status = str(item.get("status") or "unknown")
        container.state = str(item.get("state") or "unknown")
        container.health = str(item.get("health") or "")
        container.cpu_percent = float(item.get("cpu_percent") or 0)
        container.mem_usage = int(item.get("mem_usage") or 0)
        container.mem_limit = int(item.get("mem_limit") or 0)
        container.ports = json.dumps(item.get("ports") or [])
        container.created = str(item.get("created") or "")
        container.compose_project = str(item.get("compose_project") or "")
        container.updated_at = utcnow()

    if seen_ids:
        stale = (
            db.query(Container)
            .filter(Container.remote_id == remote.id, Container.docker_id.not_in(seen_ids))
            .all()
        )
        for container in stale:
            db.delete(container)
    elif payload.get("containers") is not None:
        db.query(Container).filter(Container.remote_id == remote.id).delete()

    if payload.get("updates") is not None:
        db.query(PackageUpdate).filter(PackageUpdate.remote_id == remote.id).delete()
        for item in payload.get("updates") or []:
            db.add(
                PackageUpdate(
                    id=str(uuid.uuid4()),
                    remote_id=remote.id,
                    package=str(item.get("package") or ""),
                    current_version=str(item.get("current_version") or ""),
                    new_version=str(item.get("new_version") or ""),
                    is_security=bool(item.get("is_security")),
                    origin=str(item.get("origin") or ""),
                )
            )

    db.commit()
    db.refresh(remote)
    return remote


def queue_command(
    db: Session,
    remote: Remote,
    action: str,
    target: str,
    requested_by: str,
    payload: dict[str, Any] | None = None,
) -> Task:
    task = Task(
        id=str(uuid.uuid4()),
        remote_id=remote.id,
        type=action,
        target=target,
        status="queued",
        requested_by=requested_by,
    )
    db.add(task)
    db.flush()
    db.add(
        AgentCommand(
            id=str(uuid.uuid4()),
            remote_id=remote.id,
            task_id=task.id,
            action=action,
            payload=json.dumps(payload or {}),
            status="pending",
        )
    )
    db.commit()
    db.refresh(task)
    return task


def pending_commands(db: Session, remote: Remote) -> list[tuple[AgentCommand, dict[str, Any]]]:
    rows = (
        db.query(AgentCommand)
        .filter(AgentCommand.remote_id == remote.id, AgentCommand.status == "pending")
        .order_by(AgentCommand.created_at.asc())
        .all()
    )
    result = []
    now = utcnow()
    for command in rows:
        command.status = "sent"
        task = db.get(Task, command.task_id)
        if task and task.status == "queued":
            task.status = "running"
            task.started_at = now
        try:
            payload = json.loads(command.payload or "{}")
        except json.JSONDecodeError:
            payload = {}
        result.append((command, payload))
    db.commit()
    return result


def complete_task(db: Session, remote: Remote, task_id: str, status: str, log: str, error: str) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.remote_id != remote.id:
        raise ValueError("Unknown task")
    task.status = status if status in {"ok", "error"} else "error"
    task.log = log
    task.error = error
    task.finished_at = utcnow()
    db.query(AgentCommand).filter(AgentCommand.task_id == task.id).update({"status": "done"})
    db.commit()
    db.refresh(task)
    return task


def build_dashboard(db: Session) -> DashboardOut:
    refresh_remote_status(db)
    remotes = db.query(Remote).order_by(Remote.name.asc()).all()
    remote_outs = [remote_to_out(db, remote) for remote in remotes]
    online = sum(1 for item in remote_outs if item.status == "online")
    offline = sum(1 for item in remote_outs if item.status == "offline")
    degraded = sum(1 for item in remote_outs if item.status == "degraded")
    running = sum(item.container_running for item in remote_outs)
    total = sum(item.container_total for item in remote_outs)
    updates = sum(item.updates_available for item in remote_outs)
    security = sum(item.security_updates for item in remote_outs)
    live = [item for item in remote_outs if item.status in {"online", "degraded"}]
    avg_cpu = round(sum(item.cpu_percent for item in live) / len(live), 1) if live else 0.0
    mem_vals = [
        (item.mem_used / item.mem_total) * 100 for item in live if item.mem_total > 0
    ]
    avg_mem = round(sum(mem_vals) / len(mem_vals), 1) if mem_vals else 0.0
    temps = [item.temperature_c for item in live if item.temperature_c is not None]
    since = utcnow() - timedelta(hours=24)
    failed = (
        db.query(func.count(Task.id))
        .filter(Task.status == "error", Task.created_at >= since)
        .scalar()
        or 0
    )
    running_tasks = (
        db.query(func.count(Task.id)).filter(Task.status.in_(["queued", "running"])).scalar() or 0
    )
    recent = (
        db.query(Task, Remote.name)
        .outerjoin(Remote, Task.remote_id == Remote.id)
        .order_by(Task.created_at.desc())
        .limit(12)
        .all()
    )
    outliers = [
        item
        for item in remote_outs
        if item.status in {"degraded", "offline"}
        or item.cpu_percent >= 80
        or (item.mem_total and (item.mem_used / item.mem_total) >= 0.85)
        or (item.temperature_c is not None and item.temperature_c >= 75)
        or item.updates_available > 0
        and item.security_updates > 0
    ][:8]
    return DashboardOut(
        remotes_total=len(remote_outs),
        remotes_online=online,
        remotes_offline=offline,
        remotes_degraded=degraded,
        containers_running=running,
        containers_stopped=max(total - running, 0),
        containers_total=total,
        updates_available=updates,
        security_updates=security,
        failed_tasks_24h=int(failed),
        running_tasks=int(running_tasks),
        hottest_temp_c=max(temps) if temps else None,
        avg_cpu_percent=avg_cpu,
        avg_mem_percent=avg_mem,
        remotes=remote_outs,
        recent_tasks=[task_to_out(task, name or "") for task, name in recent],
        outliers=outliers,
    )


def metric_history(db: Session, remote_id: str) -> list[MetricPoint]:
    rows = (
        db.query(MetricSample)
        .filter(MetricSample.remote_id == remote_id)
        .order_by(MetricSample.captured_at.asc())
        .all()
    )
    return [
        MetricPoint(
            captured_at=row.captured_at,
            cpu_percent=row.cpu_percent,
            mem_percent=row.mem_percent,
            disk_percent=row.disk_percent,
            load_1=row.load_1,
            temperature_c=row.temperature_c,
        )
        for row in rows
    ]


def search(db: Session, query: str, limit: int = 20) -> list[SearchHit]:
    needle = query.strip()
    if not needle:
        return []
    pattern = f"%{needle}%"
    hits: list[SearchHit] = []

    remotes = (
        db.query(Remote)
        .filter(
            or_(
                Remote.name.ilike(pattern),
                Remote.hostname.ilike(pattern),
                Remote.model.ilike(pattern),
                Remote.tags.ilike(pattern),
            )
        )
        .limit(limit)
        .all()
    )
    for remote in remotes:
        hits.append(
            SearchHit(
                kind="remote",
                id=remote.id,
                title=remote.name,
                subtitle=f"{remote.hostname or 'unregistered'} · {remote.model or remote.arch}",
                href=f"/remotes/{remote.id}",
                status=remote.status,
            )
        )

    containers = (
        db.query(Container, Remote.name)
        .join(Remote, Container.remote_id == Remote.id)
        .filter(or_(Container.name.ilike(pattern), Container.image.ilike(pattern)))
        .limit(limit)
        .all()
    )
    for container, remote_name in containers:
        hits.append(
            SearchHit(
                kind="container",
                id=container.id,
                title=container.name,
                subtitle=f"{remote_name} · {container.image}",
                href="/containers",
                status=container.state,
            )
        )

    packages = (
        db.query(PackageUpdate, Remote.name)
        .join(Remote, PackageUpdate.remote_id == Remote.id)
        .filter(PackageUpdate.package.ilike(pattern))
        .limit(limit)
        .all()
    )
    for package, remote_name in packages:
        hits.append(
            SearchHit(
                kind="update",
                id=package.id,
                title=package.package,
                subtitle=f"{remote_name} · {package.current_version} → {package.new_version}",
                href="/updates",
                status="security" if package.is_security else "available",
            )
        )

    tasks = (
        db.query(Task, Remote.name)
        .outerjoin(Remote, Task.remote_id == Remote.id)
        .filter(or_(Task.type.ilike(pattern), Task.target.ilike(pattern), Task.log.ilike(pattern)))
        .order_by(Task.created_at.desc())
        .limit(limit)
        .all()
    )
    for task, remote_name in tasks:
        hits.append(
            SearchHit(
                kind="task",
                id=task.id,
                title=f"{task.type} {task.target}".strip(),
                subtitle=f"{remote_name or 'manager'} · {task.status}",
                href="/tasks",
                status=task.status,
            )
        )

    lowered = needle.lower()

    def rank(hit: SearchHit) -> tuple[int, str]:
        title = hit.title.lower()
        if title == lowered:
            score = 0
        elif title.startswith(lowered):
            score = 1
        else:
            score = 2
        return score, hit.title.lower()

    hits.sort(key=rank)
    return hits[:limit]


def change_password(db: Session, user: User, current: str, new: str) -> None:
    if not verify_password(current, user.password_hash):
        raise ValueError("Current password is incorrect")
    user.password_hash = hash_password(new)
    db.commit()


async def emit_remote(db: Session, remote: Remote) -> None:
    await bus.publish("remote.updated", remote_to_out(db, remote).model_dump(mode="json"))


async def emit_task(task: Task, remote_name: str = "") -> None:
    await bus.publish("task.updated", task_to_out(task, remote_name).model_dump(mode="json"))


async def emit_dashboard_hint() -> None:
    await bus.publish("inventory.updated", {"at": utcnow().isoformat()})
