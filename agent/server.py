"""
╔══════════════════════════════════════════════════════════╗
║         DustOps Agent — FastAPI Local REST API            ║
║        127.0.0.1:4141 — Metrics, Processes, Actions      ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, FileResponse
import secrets
import config
import time
from collections import defaultdict
from fastapi.middleware.cors import CORSMiddleware

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.models import (
    SystemMetrics,
    ProcessInfo,
    ActionResult,
    CrashEvent,
    ProjectStatus,
    ExecRequest,
    ExecResult,
)
from agent.metrics import collect_system_metrics, discover_tracked_processes
from agent.process_manager import (
    kill_process,
    restart_service,
    list_registered_services,
)
from agent.project_manager import (
    scan_projects,
    get_project_by_id,
    restart_project,
    exec_in_project,
)
from agent.watchdog import CrashWatchdog

logger = logging.getLogger("dustops.server")

# ─── Watchdog singleton ─────────────────────────────────
watchdog = CrashWatchdog()

# Crash event buffer (consumed by the Discord bot via polling)
_crash_buffer: list[CrashEvent] = []

security = HTTPBasic()

# IP-based Anti-Bruteforce Tracking
# {ip_address: {"failures": int, "lockout_until": float}}
_auth_failures: dict[str, dict] = defaultdict(lambda: {"failures": 0, "lockout_until": 0.0})
MAX_FAILURES = 5
LOCKOUT_TIME_SECONDS = 900  # 15 minutes

def verify_auth(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    client_ip = request.client.host if request.client else "unknown"
    tracker = _auth_failures[client_ip]

    if time.time() < tracker["lockout_until"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later."
        )

    correct_user = secrets.compare_digest(credentials.username, config.WEB_USERNAME)
    correct_pass = secrets.compare_digest(credentials.password, config.WEB_PASSWORD)
    
    if not (correct_user and correct_pass):
        tracker["failures"] += 1
        if tracker["failures"] == MAX_FAILURES:
            tracker["lockout_until"] = time.time() + LOCKOUT_TIME_SECONDS
            logger.warning(f"SECURITY ALERT: IP {client_ip} locked out due to brute-force attempts!")
            
            _buffer_crash(CrashEvent(
                service_name="🚨 GÜVENLİK İHLALİ", 
                pid=0, 
                message=f"Terminalinize (Web Panele) İZİNSİZ GİRİŞ DENEMESİ gerçekleşti! IP: {client_ip}"
            ))
            
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    # Success -> reset tracker
    tracker["failures"] = 0
    tracker["lockout_until"] = 0.0
    return credentials.username


def _buffer_crash(event: CrashEvent) -> None:
    _crash_buffer.append(event)
    logger.warning("Crash buffered: %s", event.service_name)


watchdog.on_crash(_buffer_crash)


# ─── Lifespan ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    watchdog.start()
    logger.info("Core Agent started — Watchdog active")
    yield
    watchdog.stop()
    logger.info("Core Agent shutting down")


# ─── FastAPI App ─────────────────────────────────────────
app = FastAPI(
    title="DustOps Core Agent",
    version="1.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ─── Endpoints ───────────────────────────────────────────

@app.get("/")
async def serve_ui(_=Depends(verify_auth)):
    web_dir = os.path.join(os.path.dirname(__file__), "..", "web")
    return FileResponse(os.path.join(web_dir, "index.html"))

@app.get("/favicon.ico")
async def serve_favicon():
    web_dir = os.path.join(os.path.dirname(__file__), "..", "web")
    return FileResponse(os.path.join(web_dir, "favicon.ico"))


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "DustOps Core Agent", "uptime": True}


@app.get("/metrics", response_model=SystemMetrics)
async def get_metrics(_=Depends(verify_auth)):
    """Return current system-level CPU / RAM / Disk metrics."""
    return collect_system_metrics()


@app.get("/processes", response_model=list[ProcessInfo])
async def get_processes(_=Depends(verify_auth)):
    """Return all currently tracked processes."""
    return discover_tracked_processes()


@app.get("/services", response_model=list[str])
async def get_services(_=Depends(verify_auth)):
    """Return registered service names available for restart."""
    return list_registered_services()


@app.post("/kill/{pid}", response_model=ActionResult)
async def api_kill(pid: int, _=Depends(verify_auth)):
    """Kill a process by PID."""
    result = kill_process(pid)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.detail)
    return result


@app.post("/restart/{service_name}", response_model=ActionResult)
async def api_restart(service_name: str, _=Depends(verify_auth)):
    """Restart a registered service by name."""
    result = restart_service(service_name)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.detail)
    return result


@app.get("/crashes", response_model=list[CrashEvent])
async def get_crashes(_=Depends(verify_auth)):
    """Drain and return buffered crash events (consumed once)."""
    global _crash_buffer
    events = list(_crash_buffer)
    _crash_buffer = []
    return events


# ─── Project Scoped Endpoints ────────────────────────────

@app.get("/projects", response_model=list[ProjectStatus])
async def api_get_projects(_=Depends(verify_auth)):
    """Return all projects with grouped service and process details."""
    return scan_projects()


@app.get("/projects/{project_id}", response_model=ProjectStatus)
async def api_get_project(project_id: str, _=Depends(verify_auth)):
    """Return a single project with its live services."""
    projects = scan_projects()
    for p in projects:
        if p.id == project_id:
            return p
    raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")


@app.post("/projects/{project_id}/restart", response_model=ActionResult)
async def api_restart_project(project_id: str, _=Depends(verify_auth)):
    """Restart all services belonging to the specified project."""
    res = await restart_project(project_id)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.detail)
    return res


@app.post("/projects/{project_id}/exec", response_model=ExecResult)
async def api_exec_project(project_id: str, payload: ExecRequest, _=Depends(verify_auth)):
    """Execute a shell command inside the project's root working directory."""
    if not payload.command or not payload.command.strip():
        raise HTTPException(status_code=400, detail="Command cannot be empty.")
    
    res = await exec_in_project(project_id, payload.command.strip())
    return res

