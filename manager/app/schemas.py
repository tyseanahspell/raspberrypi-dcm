from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class UserOut(BaseModel):
    username: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


class RemoteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    notes: str = ""
    tags: str = ""


class RemoteOut(BaseModel):
    id: str
    name: str
    hostname: str
    status: str
    last_seen: datetime | None
    os_pretty: str
    kernel: str
    arch: str
    model: str
    tags: str
    notes: str
    cpu_percent: float
    mem_used: int
    mem_total: int
    disk_used: int
    disk_total: int
    load_1: float
    load_5: float
    load_15: float
    temperature_c: float | None
    uptime_seconds: int
    cpu_count: int
    under_voltage: bool
    thermal_throttled: bool
    docker_available: bool
    container_running: int = 0
    container_total: int = 0
    updates_available: int = 0
    security_updates: int = 0

    model_config = {"from_attributes": True}


class RemoteCreated(RemoteOut):
    agent_token: str


class ContainerOut(BaseModel):
    id: str
    remote_id: str
    remote_name: str = ""
    docker_id: str
    name: str
    image: str
    status: str
    state: str
    health: str
    cpu_percent: float
    mem_usage: int
    mem_limit: int
    ports: list[dict[str, Any]] = []
    created: str
    compose_project: str

    model_config = {"from_attributes": True}


class MetricPoint(BaseModel):
    captured_at: datetime
    cpu_percent: float
    mem_percent: float
    disk_percent: float
    load_1: float
    temperature_c: float | None


class PackageUpdateOut(BaseModel):
    id: str
    remote_id: str
    remote_name: str = ""
    package: str
    current_version: str
    new_version: str
    is_security: bool
    origin: str

    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: str
    remote_id: str | None
    remote_name: str = ""
    type: str
    target: str
    status: str
    requested_by: str
    log: str
    error: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class SearchHit(BaseModel):
    kind: str
    id: str
    title: str
    subtitle: str
    href: str
    status: str = ""


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


class DashboardOut(BaseModel):
    remotes_total: int
    remotes_online: int
    remotes_offline: int
    remotes_degraded: int
    containers_running: int
    containers_stopped: int
    containers_total: int
    updates_available: int
    security_updates: int
    failed_tasks_24h: int
    running_tasks: int
    hottest_temp_c: float | None
    avg_cpu_percent: float
    avg_mem_percent: float
    remotes: list[RemoteOut]
    recent_tasks: list[TaskOut]
    outliers: list[RemoteOut]


class EnrollmentOut(BaseModel):
    enrollment_token: str


class AgentEnrollRequest(BaseModel):
    enrollment_token: str
    hostname: str
    name: str | None = None


class AgentEnrollResponse(BaseModel):
    agent_id: str
    agent_token: str
    remote_id: str
    name: str


class AgentHeartbeat(BaseModel):
    metrics: dict[str, Any]
    containers: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] | None = None
    identity: dict[str, Any] = {}


class AgentCommandOut(BaseModel):
    id: str
    task_id: str
    action: str
    payload: dict[str, Any]


class AgentTaskResult(BaseModel):
    task_id: str
    status: str
    log: str = ""
    error: str = ""
