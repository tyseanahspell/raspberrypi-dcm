from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_agent
from app.models import Remote
from app.schemas import (
    AgentCommandOut,
    AgentEnrollRequest,
    AgentEnrollResponse,
    AgentHeartbeat,
    AgentTaskResult,
    TaskOut,
)
from app.services import (
    apply_heartbeat,
    complete_task,
    emit_dashboard_hint,
    emit_remote,
    emit_task,
    enroll_agent,
    pending_commands,
    task_to_out,
)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/enroll", response_model=AgentEnrollResponse)
def enroll(body: AgentEnrollRequest, db: Session = Depends(get_db)) -> AgentEnrollResponse:
    try:
        remote, token = enroll_agent(db, body.enrollment_token, body.hostname, body.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return AgentEnrollResponse(
        agent_id=remote.agent_id,
        agent_token=token,
        remote_id=remote.id,
        name=remote.name,
    )


@router.post("/heartbeat")
async def heartbeat(
    body: AgentHeartbeat,
    remote: Remote = Depends(get_current_agent),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    remote = apply_heartbeat(db, remote, body.model_dump())
    await emit_remote(db, remote)
    await emit_dashboard_hint()
    return {"status": "ok", "remote_id": remote.id}


@router.get("/commands", response_model=list[AgentCommandOut])
def commands(
    remote: Remote = Depends(get_current_agent),
    db: Session = Depends(get_db),
) -> list[AgentCommandOut]:
    rows = pending_commands(db, remote)
    return [
        AgentCommandOut(id=command.id, task_id=command.task_id, action=command.action, payload=payload)
        for command, payload in rows
    ]


@router.post("/task-result", response_model=TaskOut)
async def task_result(
    body: AgentTaskResult,
    remote: Remote = Depends(get_current_agent),
    db: Session = Depends(get_db),
) -> TaskOut:
    try:
        task = complete_task(db, remote, body.task_id, body.status, body.log, body.error)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await emit_task(task, remote.name)
    await emit_dashboard_hint()
    return task_to_out(task, remote.name)
