"""
╔══════════════════════════════════════════════════════════╗
║            DustOps — Shared Pydantic Models              ║
║       Canonical schemas shared across all modules        ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from datetime import datetime


class SystemMetrics(BaseModel):
    """Snapshot of system-level resource utilisation."""
    cpu_percent: float = Field(description="Overall CPU usage %")
    ram_used_mb: float = Field(description="RAM used in megabytes")
    ram_total_mb: float = Field(description="Total RAM in megabytes")
    ram_percent: float = Field(description="RAM usage %")
    disk_used_gb: float = Field(description="Disk used in GB")
    disk_total_gb: float = Field(description="Total disk in GB")
    disk_percent: float = Field(description="Disk usage %")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ProcessInfo(BaseModel):
    """A single tracked process entry."""
    pid: int
    name: str
    cmdline: str = ""
    cpu_percent: float = 0.0
    ram_mb: float = 0.0
    port: int | None = None
    status: str = "running"
    create_time: float = 0.0


class CrashEvent(BaseModel):
    """Emitted when a tracked process dies unexpectedly."""
    service_name: str
    pid: int
    exit_code: int | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message: str = ""


class ActionResult(BaseModel):
    """Generic response for kill / restart actions."""
    success: bool
    action: str
    target: str
    detail: str = ""


# ─── Project & Service Grouping Models ──────────────────
class ServiceDef(BaseModel):
    name: str
    match: str
    port: int | None = None
    restart_cmd: str


class ProjectDef(BaseModel):
    id: str
    name: str
    cwd: str
    services: list[ServiceDef] = Field(default_factory=list)


class ServiceStatus(BaseModel):
    name: str
    port: int | None = None
    status: str = "stopped"  # "running" | "stopped"
    process: ProcessInfo | None = None
    restart_cmd: str


class ProjectStatus(BaseModel):
    id: str
    name: str
    cwd: str
    services: list[ServiceStatus] = Field(default_factory=list)
    is_healthy: bool = True


class ExecRequest(BaseModel):
    command: str


class ExecResult(BaseModel):
    success: bool
    command: str
    cwd: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    error: str | None = None

