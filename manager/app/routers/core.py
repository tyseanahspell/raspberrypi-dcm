from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Container, PackageUpdate, Remote, Task, User
from app.schemas import (
    ContainerOut,
    DashboardOut,
    EnrollmentOut,
    MetricPoint,
    PackageUpdateOut,
    RemoteCreated,
    RemoteCreate,
    RemoteOut,
    SearchResponse,
    TaskOut,
)
from app.services import (
    build_dashboard,
    container_to_out,
    create_remote,
    emit_dashboard_hint,
    emit_task,
    get_enrollment_token,
    metric_history,
    queue_command,
    refresh_remote_status,
    remote_to_out,
    rotate_enrollment_token,
    search,
    task_to_out,
)

router = APIRouter(tags=["core"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DashboardOut:
    return build_dashboard(db)


@router.get("/search", response_model=SearchResponse)
def global_search(
    q: str = Query(min_length=1, max_length=128),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SearchResponse:
    return SearchResponse(query=q, hits=search(db, q))


@router.get("/remotes", response_model=list[RemoteOut])
def list_remotes(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[RemoteOut]:
    refresh_remote_status(db)
    remotes = db.query(Remote).order_by(Remote.name.asc()).all()
    return [remote_to_out(db, remote) for remote in remotes]


@router.post("/remotes", response_model=RemoteCreated, status_code=status.HTTP_201_CREATED)
def add_remote(
    body: RemoteCreate,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RemoteCreated:
    remote, token = create_remote(db, body.name, body.notes, body.tags)
    out = remote_to_out(db, remote)
    return RemoteCreated(**out.model_dump(), agent_token=token)


@router.get("/remotes/{remote_id}", response_model=RemoteOut)
def get_remote(
    remote_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RemoteOut:
    remote = db.get(Remote, remote_id)
    if remote is None:
        raise HTTPException(status_code=404, detail="Remote not found")
    refresh_remote_status(db, remote)
    return remote_to_out(db, remote)


@router.get("/remotes/{remote_id}/metrics", response_model=list[MetricPoint])
def remote_metrics(
    remote_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MetricPoint]:
    if db.get(Remote, remote_id) is None:
        raise HTTPException(status_code=404, detail="Remote not found")
    return metric_history(db, remote_id)


@router.delete("/remotes/{remote_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_remote(
    remote_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    remote = db.get(Remote, remote_id)
    if remote is None:
        raise HTTPException(status_code=404, detail="Remote not found")
    db.delete(remote)
    db.commit()
    await emit_dashboard_hint()


@router.post("/remotes/{remote_id}/{action}", response_model=TaskOut)
async def remote_power(
    remote_id: str,
    action: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskOut:
    if action not in {"reboot", "shutdown"}:
        raise HTTPException(status_code=404, detail="Unknown action")
    remote = db.get(Remote, remote_id)
    if remote is None:
        raise HTTPException(status_code=404, detail="Remote not found")
    task = queue_command(db, remote, action, remote.name, user.username)
    await emit_task(task, remote.name)
    return task_to_out(task, remote.name)


@router.get("/containers", response_model=list[ContainerOut])
def list_containers(
    remote_id: str | None = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ContainerOut]:
    query = db.query(Container, Remote.name).join(Remote, Container.remote_id == Remote.id)
    if remote_id:
        query = query.filter(Container.remote_id == remote_id)
    rows = query.order_by(Remote.name.asc(), Container.name.asc()).all()
    return [container_to_out(container, name) for container, name in rows]


@router.post("/containers/{container_id}/{action}", response_model=TaskOut)
async def container_action(
    container_id: str,
    action: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskOut:
    if action not in {"start", "stop", "restart"}:
        raise HTTPException(status_code=404, detail="Unknown action")
    container = db.get(Container, container_id)
    if container is None:
        raise HTTPException(status_code=404, detail="Container not found")
    remote = db.get(Remote, container.remote_id)
    if remote is None:
        raise HTTPException(status_code=404, detail="Remote not found")
    task = queue_command(
        db,
        remote,
        f"container_{action}",
        container.name,
        user.username,
        {"docker_id": container.docker_id, "name": container.name},
    )
    await emit_task(task, remote.name)
    return task_to_out(task, remote.name)


@router.get("/updates", response_model=list[PackageUpdateOut])
def list_updates(
    remote_id: str | None = None,
    security: bool | None = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PackageUpdateOut]:
    query = db.query(PackageUpdate, Remote.name).join(Remote, PackageUpdate.remote_id == Remote.id)
    if remote_id:
        query = query.filter(PackageUpdate.remote_id == remote_id)
    if security is True:
        query = query.filter(PackageUpdate.is_security.is_(True))
    rows = query.order_by(PackageUpdate.is_security.desc(), PackageUpdate.package.asc()).all()
    return [
        PackageUpdateOut(
            id=item.id,
            remote_id=item.remote_id,
            remote_name=name,
            package=item.package,
            current_version=item.current_version,
            new_version=item.new_version,
            is_security=item.is_security,
            origin=item.origin,
        )
        for item, name in rows
    ]


@router.post("/updates/refresh", response_model=list[TaskOut])
async def refresh_updates(
    remote_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TaskOut]:
    query = db.query(Remote)
    if remote_id:
        query = query.filter(Remote.id == remote_id)
    remotes = query.all()
    if remote_id and not remotes:
        raise HTTPException(status_code=404, detail="Remote not found")
    tasks = []
    for remote in remotes:
        task = queue_command(db, remote, "refresh_updates", remote.name, user.username)
        await emit_task(task, remote.name)
        tasks.append(task_to_out(task, remote.name))
    return tasks


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(
    remote_id: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TaskOut]:
    query = db.query(Task, Remote.name).outerjoin(Remote, Task.remote_id == Remote.id)
    if remote_id:
        query = query.filter(Task.remote_id == remote_id)
    if status_filter:
        query = query.filter(Task.status == status_filter)
    rows = query.order_by(Task.created_at.desc()).limit(300).all()
    return [task_to_out(task, name or "") for task, name in rows]


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(
    task_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskOut:
    row = (
        db.query(Task, Remote.name)
        .outerjoin(Remote, Task.remote_id == Remote.id)
        .filter(Task.id == task_id)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task, name = row
    return task_to_out(task, name or "")


@router.get("/settings/enrollment-token", response_model=EnrollmentOut)
def enrollment_token(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EnrollmentOut:
    return EnrollmentOut(enrollment_token=get_enrollment_token(db))


@router.post("/settings/enrollment-token/rotate", response_model=EnrollmentOut)
def rotate_token(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EnrollmentOut:
    return EnrollmentOut(enrollment_token=rotate_enrollment_token(db))
