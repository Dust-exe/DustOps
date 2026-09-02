"""
╔══════════════════════════════════════════════════════════╗
║          DustOps Agent — System Metrics Collector         ║
║       CPU, RAM, Disk snapshots + per-process stats       ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import psutil
from datetime import datetime

from shared.models import SystemMetrics, ProcessInfo

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


# ─── System-Level Metrics ────────────────────────────────
def collect_system_metrics() -> SystemMetrics:
    """Collect a single snapshot of CPU / RAM / Disk."""
    cpu = psutil.cpu_percent(interval=0.4)
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return SystemMetrics(
        cpu_percent=cpu,
        ram_used_mb=round(vm.used / (1024 ** 2), 1),
        ram_total_mb=round(vm.total / (1024 ** 2), 1),
        ram_percent=vm.percent,
        disk_used_gb=round(disk.used / (1024 ** 3), 2),
        disk_total_gb=round(disk.total / (1024 ** 3), 2),
        disk_percent=disk.percent,
        timestamp=datetime.utcnow(),
    )


# ─── Process Discovery ──────────────────────────────────
def _get_listening_port(proc: psutil.Process) -> int | None:
    """Return the first listening TCP port for a process, or None."""
    try:
        for conn in proc.net_connections(kind="tcp"):
            if conn.status == psutil.CONN_LISTEN:
                return conn.laddr.port
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        pass
    return None


def _matches_keywords(proc: psutil.Process, keywords: list[str]) -> bool:
    """Check if process name or cmdline contains any watched keyword."""
    try:
        name_lower = proc.name().lower()
        cmdline_lower = " ".join(proc.cmdline()).lower()
        for kw in keywords:
            if kw in name_lower or kw in cmdline_lower:
                return True
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass
    return False


def _matches_ports(proc: psutil.Process, ports: list[int]) -> bool:
    """Check if process is listening on any watched port."""
    port = _get_listening_port(proc)
    return port is not None and port in ports


def discover_tracked_processes(
    keywords: list[str] | None = None,
    ports: list[int] | None = None,
) -> list[ProcessInfo]:
    """
    Scan all running processes and return those matching
    the configured keywords or port bindings.
    """
    kw = keywords if keywords is not None else config.WATCH_KEYWORDS
    pt = ports if ports is not None else config.WATCH_PORTS

    tracked: list[ProcessInfo] = []

    for proc in psutil.process_iter(["pid", "name", "status"]):
        try:
            if not (_matches_keywords(proc, kw) or _matches_ports(proc, pt)):
                continue

            with proc.oneshot():
                info = ProcessInfo(
                    pid=proc.pid,
                    name=proc.name(),
                    cmdline=" ".join(proc.cmdline()[:6]),
                    cpu_percent=round(proc.cpu_percent(interval=0), 2),
                    ram_mb=round(proc.memory_info().rss / (1024 ** 2), 1),
                    port=_get_listening_port(proc),
                    status=proc.status(),
                    create_time=proc.create_time(),
                )
            tracked.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return tracked
