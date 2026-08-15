from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Remote(Base):
    __tablename__ = "remotes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    hostname: Mapped[str] = mapped_column(String(255), default="")
    agent_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    os_pretty: Mapped[str] = mapped_column(String(255), default="")
    kernel: Mapped[str] = mapped_column(String(128), default="")
    arch: Mapped[str] = mapped_column(String(32), default="")
    model: Mapped[str] = mapped_column(String(255), default="")
    tags: Mapped[str] = mapped_column(String(255), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    cpu_percent: Mapped[float] = mapped_column(Float, default=0.0)
    mem_used: Mapped[int] = mapped_column(BigInteger, default=0)
    mem_total: Mapped[int] = mapped_column(BigInteger, default=0)
    disk_used: Mapped[int] = mapped_column(BigInteger, default=0)
    disk_total: Mapped[int] = mapped_column(BigInteger, default=0)
    load_1: Mapped[float] = mapped_column(Float, default=0.0)
    load_5: Mapped[float] = mapped_column(Float, default=0.0)
    load_15: Mapped[float] = mapped_column(Float, default=0.0)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    uptime_seconds: Mapped[int] = mapped_column(Integer, default=0)
    net_rx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    net_tx_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    cpu_count: Mapped[int] = mapped_column(Integer, default=0)
    throttled: Mapped[str] = mapped_column(String(32), default="")
    under_voltage: Mapped[bool] = mapped_column(Boolean, default=False)
    thermal_throttled: Mapped[bool] = mapped_column(Boolean, default=False)
    docker_available: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    containers: Mapped[list[Container]] = relationship(
        back_populates="remote", cascade="all, delete-orphan"
    )
    metrics: Mapped[list[MetricSample]] = relationship(
        back_populates="remote", cascade="all, delete-orphan"
    )
    packages: Mapped[list[PackageUpdate]] = relationship(
        back_populates="remote", cascade="all, delete-orphan"
    )
    tasks: Mapped[list[Task]] = relationship(back_populates="remote", cascade="all, delete-orphan")
    commands: Mapped[list[AgentCommand]] = relationship(
        back_populates="remote", cascade="all, delete-orphan"
    )


class Container(Base):
    __tablename__ = "containers"
    __table_args__ = (Index("ix_containers_remote_name", "remote_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    remote_id: Mapped[str] = mapped_column(ForeignKey("remotes.id", ondelete="CASCADE"), index=True)
    docker_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    image: Mapped[str] = mapped_column(String(512), default="")
    status: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    state: Mapped[str] = mapped_column(String(32), default="unknown")
    health: Mapped[str] = mapped_column(String(32), default="")
    cpu_percent: Mapped[float] = mapped_column(Float, default=0.0)
    mem_usage: Mapped[int] = mapped_column(BigInteger, default=0)
    mem_limit: Mapped[int] = mapped_column(BigInteger, default=0)
    ports: Mapped[str] = mapped_column(Text, default="[]")
    created: Mapped[str] = mapped_column(String(64), default="")
    compose_project: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    remote: Mapped[Remote] = relationship(back_populates="containers")


class MetricSample(Base):
    __tablename__ = "metric_samples"
    __table_args__ = (Index("ix_metrics_remote_ts", "remote_id", "captured_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    remote_id: Mapped[str] = mapped_column(ForeignKey("remotes.id", ondelete="CASCADE"), index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    cpu_percent: Mapped[float] = mapped_column(Float, default=0.0)
    mem_percent: Mapped[float] = mapped_column(Float, default=0.0)
    disk_percent: Mapped[float] = mapped_column(Float, default=0.0)
    load_1: Mapped[float] = mapped_column(Float, default=0.0)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)

    remote: Mapped[Remote] = relationship(back_populates="metrics")


class PackageUpdate(Base):
    __tablename__ = "package_updates"
    __table_args__ = (Index("ix_updates_remote_pkg", "remote_id", "package"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    remote_id: Mapped[str] = mapped_column(ForeignKey("remotes.id", ondelete="CASCADE"), index=True)
    package: Mapped[str] = mapped_column(String(255), index=True)
    current_version: Mapped[str] = mapped_column(String(128), default="")
    new_version: Mapped[str] = mapped_column(String(128), default="")
    is_security: Mapped[bool] = mapped_column(Boolean, default=False)
    origin: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    remote: Mapped[Remote] = relationship(back_populates="packages")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_created", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    remote_id: Mapped[str | None] = mapped_column(
        ForeignKey("remotes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    requested_by: Mapped[str] = mapped_column(String(64), default="system")
    log: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    remote: Mapped[Remote | None] = relationship(back_populates="tasks")


class AgentCommand(Base):
    __tablename__ = "agent_commands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    remote_id: Mapped[str] = mapped_column(ForeignKey("remotes.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(64))
    payload: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    remote: Mapped[Remote] = relationship(back_populates="commands")
