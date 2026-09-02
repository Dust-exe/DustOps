"""
╔══════════════════════════════════════════════════════════╗
║        DustOps Agent — Project & Service Manager         ║
║  Scoped Process Matching, Targeted Restarts & Exec       ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import psutil

from shared.models import (
    ProjectDef,
    ServiceDef,
    ProjectStatus,
    ServiceStatus,
    ProcessInfo,
    ActionResult,
    ExecResult,
)
from agent.metrics import _get_listening_port

logger = logging.getLogger("dustops.project_manager")

PROJECTS_FILE = Path(__file__).resolve().parent.parent / "projects.json"


def load_projects_config() -> list[ProjectDef]:
    """Load project definitions from projects.json."""
    if not PROJECTS_FILE.exists():
        logger.warning("projects.json not found at %s", PROJECTS_FILE)
        return []

    try:
        with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [ProjectDef(**p) for p in data.get("projects", [])]
    except Exception as exc:
        logger.exception("Failed to parse projects.json: %s", exc)
        return []


def _normalize_path(p: str) -> str:
    try:
        return os.path.realpath(p).rstrip("/")
    except Exception:
        return p.rstrip("/")


def scan_projects() -> list[ProjectStatus]:
    """
    Map currently active system processes to registered projects and services
    based on cwd, cmdline, and ports.
    """
    project_defs = load_projects_config()
    if not project_defs:
        return []

    # Gather active processes once
    proc_snapshots: list[tuple[psutil.Process, str, str, str, int | None]] = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            with proc.oneshot():
                p_cwd = ""
                try:
                    p_cwd = _normalize_path(proc.cwd())
                except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                    pass

                cmdline_parts = proc.cmdline()
                cmdline_str = " ".join(cmdline_parts) if cmdline_parts else ""
                p_name = proc.name().lower()
                port = _get_listening_port(proc)
                proc_snapshots.append((proc, p_cwd, cmdline_str, p_name, port))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    project_statuses: list[ProjectStatus] = []

    for pdef in project_defs:
        proj_cwd = _normalize_path(pdef.cwd)
        service_statuses: list[ServiceStatus] = []

        for sdef in pdef.services:
            matched_proc_info: ProcessInfo | None = None
            match_target = sdef.match.lower()

            for proc, p_cwd, cmdline_str, p_name, port in proc_snapshots:
                # 1. Port match has priority
                if sdef.port is not None and port == sdef.port:
                    pass
                else:
                    # 2. CWD + match string
                    cwd_match = (
                        proj_cwd and (p_cwd == proj_cwd or p_cwd.startswith(proj_cwd + "/"))
                    ) or (proj_cwd and proj_cwd in cmdline_str)

                    # Match keyword against cmdline or name
                    text_match = (
                        match_target in cmdline_str.lower() or match_target in p_name
                    )

                    if not (cwd_match and text_match):
                        # If cwd didn't match directly, allow strong cmdline match
                        if not (match_target in cmdline_str.lower() and len(match_target) > 5):
                            continue

                # Found matching process!
                try:
                    with proc.oneshot():
                        matched_proc_info = ProcessInfo(
                            pid=proc.pid,
                            name=proc.name(),
                            cmdline=" ".join(proc.cmdline()[:6]),
                            cpu_percent=round(proc.cpu_percent(interval=0), 2),
                            ram_mb=round(proc.memory_info().rss / (1024**2), 1),
                            port=port,
                            status=proc.status(),
                            create_time=proc.create_time(),
                        )
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    matched_proc_info = None

            is_running = matched_proc_info is not None
            service_statuses.append(
                ServiceStatus(
                    name=sdef.name,
                    port=sdef.port,
                    status="running" if is_running else "stopped",
                    process=matched_proc_info,
                    restart_cmd=sdef.restart_cmd,
                )
            )

        all_running = all(s.status == "running" for s in service_statuses) if service_statuses else False
        project_statuses.append(
            ProjectStatus(
                id=pdef.id,
                name=pdef.name,
                cwd=pdef.cwd,
                services=service_statuses,
                is_healthy=all_running,
            )
        )

    return project_statuses


def get_project_by_id(project_id: str) -> ProjectDef | None:
    for p in load_projects_config():
        if p.id == project_id:
            return p
    return None


async def execute_delayed_restart(cmd: str, cwd: str | None, delay: float = 1.0):
    """Execute restart command after a small delay to allow HTTP response to finish."""
    await asyncio.sleep(delay)
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    except Exception as e:
        logger.error("Error in delayed restart (%s): %s", cmd, e)


async def restart_project(project_id: str) -> ActionResult:
    """Trigger the restart commands configured for the given project."""
    project = get_project_by_id(project_id)
    if not project:
        return ActionResult(
            success=False,
            action="restart",
            target=project_id,
            detail=f"Project '{project_id}' not found in projects.json.",
        )

    commands = [s.restart_cmd for s in project.services if s.restart_cmd]
    if not commands:
        return ActionResult(
            success=False,
            action="restart",
            target=project.name,
            detail="No restart_cmd configured for any service in this project.",
        )

    combined_cmd = " && ".join(commands)
    is_self_restart = "dustops-agent" in combined_cmd

    if is_self_restart:
        logger.info("Self-restart triggered for dustops-agent. Scheduling delayed execution.")
        asyncio.create_task(
            execute_delayed_restart(combined_cmd, cwd=project.cwd, delay=1.0)
        )
        return ActionResult(
            success=True,
            action="restart",
            target=project.name,
            detail="Self-restart scheduled. Core Agent will restart in 1 second.",
        )

    try:
        proc = await asyncio.create_subprocess_shell(
            combined_cmd,
            cwd=project.cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            if proc.returncode == 0:
                return ActionResult(
                    success=True,
                    action="restart",
                    target=project.name,
                    detail=f"Restart succeeded. Executed: `{combined_cmd}`",
                )
            else:
                err_msg = stderr.decode("utf-8", errors="replace").strip()
                return ActionResult(
                    success=False,
                    action="restart",
                    target=project.name,
                    detail=f"Exit code {proc.returncode}: {err_msg[:300]}",
                )
        except asyncio.TimeoutError:
            proc.kill()
            return ActionResult(
                success=False,
                action="restart",
                target=project.name,
                detail="Restart command timed out after 30 seconds.",
            )
    except Exception as exc:
        logger.exception("Failed to restart project %s", project_id)
        return ActionResult(
            success=False,
            action="restart",
            target=project.name,
            detail=str(exc),
        )


async def exec_in_project(project_id: str, command: str) -> ExecResult:
    """
    Safely execute a shell command inside the project's root working directory (cwd)
    with a 30-second timeout.
    """
    project = get_project_by_id(project_id)
    if not project:
        return ExecResult(
            success=False,
            command=command,
            cwd="",
            error=f"Project '{project_id}' not found in projects.json.",
        )

    if not os.path.exists(project.cwd):
        return ExecResult(
            success=False,
            command=command,
            cwd=project.cwd,
            error=f"Project directory '{project.cwd}' does not exist on disk.",
        )

    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=project.cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=30.0
            )
            stdout_str = stdout_bytes.decode("utf-8", errors="replace")
            stderr_str = stderr_bytes.decode("utf-8", errors="replace")
            return ExecResult(
                success=(proc.returncode == 0),
                command=command,
                cwd=project.cwd,
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=proc.returncode,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return ExecResult(
                success=False,
                command=command,
                cwd=project.cwd,
                error="Komut 30 saniye zaman aşımına uğradı.",
            )
    except Exception as exc:
        logger.exception("Failed executing command in %s: %s", project.cwd, exc)
        return ExecResult(
            success=False,
            command=command,
            cwd=project.cwd,
            error=str(exc),
        )
