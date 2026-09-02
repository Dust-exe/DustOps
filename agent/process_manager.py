"""
╔══════════════════════════════════════════════════════════╗
║          DustOps Agent — Process Manager                 ║
║     Kill / Restart actions via PID or service name       ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import os
import signal
import subprocess
import psutil

from shared.models import ActionResult


# ─── Kill by PID ─────────────────────────────────────────
def kill_process(pid: int) -> ActionResult:
    """Send SIGTERM (then SIGKILL on Windows) to a process."""
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except psutil.TimeoutExpired:
            proc.kill()

        return ActionResult(
            success=True,
            action="kill",
            target=f"{name} (PID {pid})",
            detail=f"Process {pid} ({name}) terminated successfully.",
        )
    except psutil.NoSuchProcess:
        return ActionResult(
            success=False,
            action="kill",
            target=f"PID {pid}",
            detail=f"Process {pid} does not exist.",
        )
    except psutil.AccessDenied:
        return ActionResult(
            success=False,
            action="kill",
            target=f"PID {pid}",
            detail=f"Access denied when trying to kill PID {pid}.",
        )
    except Exception as exc:
        return ActionResult(
            success=False,
            action="kill",
            target=f"PID {pid}",
            detail=str(exc),
        )


# ─── Service Restart Map ────────────────────────────────
# Maps a friendly service name → shell command to restart.
# Users should extend this dict via config or a JSON file.
_SERVICE_RESTART_COMMANDS: dict[str, str] = {
    "dust-studio-bot": "cd /root/dust-studio && node src/index.js &",
    "dust-studio-kayit": "cd '/root/dust studio kayıt' && node src/index.js &",
    "dustops-agent": "cd /root/DustOps && python run_agent.py &",
}


def register_restart_command(service_name: str, command: str) -> None:
    """Register or overwrite a restart command for a service."""
    _SERVICE_RESTART_COMMANDS[service_name] = command


def restart_service(service_name: str) -> ActionResult:
    """
    Restart a named service.

    Strategy:
    1. Look up the restart command from the map.
    2. Optionally kill existing processes matching the service name.
    3. Spawn the restart command in a detached subprocess.
    """
    cmd = _SERVICE_RESTART_COMMANDS.get(service_name)
    if not cmd:
        return ActionResult(
            success=False,
            action="restart",
            target=service_name,
            detail=(
                f"No restart command registered for '{service_name}'. "
                f"Available: {list(_SERVICE_RESTART_COMMANDS.keys())}"
            ),
        )

    # Attempt to kill any existing instances first
    killed_pids: list[int] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline_str = " ".join(proc.cmdline()).lower()
            if service_name.lower().replace("-", " ") in cmdline_str:
                proc.terminate()
                killed_pids.append(proc.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Spawn the restart command
    try:
        subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        detail = f"Restart command dispatched."
        if killed_pids:
            detail += f" Killed previous PIDs: {killed_pids}."

        return ActionResult(
            success=True,
            action="restart",
            target=service_name,
            detail=detail,
        )
    except Exception as exc:
        return ActionResult(
            success=False,
            action="restart",
            target=service_name,
            detail=f"Failed to spawn restart: {exc}",
        )


def list_registered_services() -> list[str]:
    """Return all registered service names."""
    return list(_SERVICE_RESTART_COMMANDS.keys())
