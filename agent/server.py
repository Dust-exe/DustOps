"""
╔══════════════════════════════════════════════════════════╗
║         DustOps Agent — FastAPI Local REST API            ║
║        127.0.0.1:4141 — Metrics, Processes, Actions      ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import logging
import asyncio
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, status, Request, Query
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
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
    LoginRequest,
    LoginResponse,
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
from agent.port_prober import probe_all_services
from agent.history_recorder import init_db, record_snapshot, get_history, get_top_consumers

logger = logging.getLogger("dustops.server")

# ─── Watchdog singleton ─────────────────────────────────
watchdog = CrashWatchdog()

# Crash event buffer (consumed by the Discord bot via polling)
_crash_buffer: list[CrashEvent] = []

security = HTTPBasic(auto_error=False)

# Active Session Tokens: {token: expire_timestamp}
_active_sessions: dict[str, float] = {}

# IP-based Anti-Bruteforce Tracking
# {ip_address: {"failures": int, "lockout_until": float}}
_auth_failures: dict[str, dict] = defaultdict(lambda: {"failures": 0, "lockout_until": 0.0})
MAX_FAILURES = 5
LOCKOUT_TIME_SECONDS = 900  # 15 minutes


def verify_auth(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(security),
    token: str | None = Query(None),
):
    """
    Unified Authentication: Supports Bearer Token, Session Cookie,
    URL query token (for SSE), or legacy HTTP Basic Auth.
    """
    client_ip = request.client.host if request.client else "unknown"
    tracker = _auth_failures[client_ip]

    if time.time() < tracker["lockout_until"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later."
        )

    # 1. Check Bearer Token in Authorization header
    auth_header = request.headers.get("Authorization", "")
    bearer_token = None
    if auth_header.startswith("Bearer "):
        bearer_token = auth_header[7:].strip()
    elif token:
        bearer_token = token.strip()
    elif "dustops_session" in request.cookies:
        bearer_token = request.cookies["dustops_session"]

    if bearer_token:
        exp = _active_sessions.get(bearer_token)
        if exp and time.time() < exp:
            tracker["failures"] = 0
            return config.WEB_USERNAME

    # 2. Check Basic Auth credentials
    if credentials:
        correct_user = secrets.compare_digest(credentials.username, config.WEB_USERNAME)
        correct_pass = secrets.compare_digest(credentials.password, config.WEB_PASSWORD)
        if correct_user and correct_pass:
            tracker["failures"] = 0
            return credentials.username

    # Authentication failed
    tracker["failures"] += 1
    if tracker["failures"] >= MAX_FAILURES:
        tracker["lockout_until"] = time.time() + LOCKOUT_TIME_SECONDS
        logger.warning(f"SECURITY ALERT: IP {client_ip} locked out due to brute-force attempts!")
        _buffer_crash(CrashEvent(
            service_name="🚨 GÜVENLİK İHLALİ", 
            pid=0, 
            message=f"Terminalinize (Web Panele) İZİNSİZ GİRİŞ DENEMESİ gerçekleşti! IP: {client_ip}"
        ))

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Valid credentials or Bearer token required.",
    )


def _buffer_crash(event: CrashEvent) -> None:
    _crash_buffer.append(event)
    logger.warning("Crash buffered: %s", event.service_name)


watchdog.on_crash(_buffer_crash)


# ─── Lifespan ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    watchdog.start()
    logger.info("Core Agent started — Watchdog & Telemetry DB active")
    yield
    watchdog.stop()
    logger.info("Core Agent shutting down")


# ─── FastAPI App ─────────────────────────────────────────
app = FastAPI(
    title="DustOps Core Agent",
    version="2.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# ─── Web UI & Static Endpoints ───────────────────────────

@app.get("/")
async def serve_ui():
    """Serves the Cosmic Dust UI without native browser basic auth blocking."""
    web_dir = os.path.join(os.path.dirname(__file__), "..", "web")
    return FileResponse(os.path.join(web_dir, "index.html"))

@app.get("/favicon.ico")
async def serve_favicon():
    web_dir = os.path.join(os.path.dirname(__file__), "..", "web")
    fav = os.path.join(web_dir, "favicon.ico")
    if os.path.exists(fav):
        return FileResponse(fav)
    return HTMLResponse("", status_code=204)


@app.get("/health")
async def health():
    return {"status": "ok", "agent": "DustOps Core Agent", "uptime": True}


# ─── Authentication Endpoints ────────────────────────────

@app.post("/auth/login", response_model=LoginResponse)
async def api_login(req: LoginRequest, request: Request):
    """Authenticate and issue a 7-day session token."""
    client_ip = request.client.host if request.client else "unknown"
    tracker = _auth_failures[client_ip]

    if time.time() < tracker["lockout_until"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Lockout active."
        )

    correct_user = secrets.compare_digest(req.username, config.WEB_USERNAME)
    correct_pass = secrets.compare_digest(req.password, config.WEB_PASSWORD)

    if not (correct_user and correct_pass):
        tracker["failures"] += 1
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya şifre hatalı."
        )

    # Success
    tracker["failures"] = 0
    tracker["lockout_until"] = 0.0
    token = secrets.token_urlsafe(32)
    # 7-day session
    _active_sessions[token] = time.time() + (7 * 86400)

    logger.info("User '%s' successfully logged in from IP %s", req.username, client_ip)
    return LoginResponse(
        success=True,
        token=token,
        username=req.username,
        detail="Giriş başarılı."
    )


@app.post("/auth/logout")
async def api_logout(request: Request):
    """Revoke active session token."""
    auth_header = request.headers.get("Authorization", "")
    token = None
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    if token and token in _active_sessions:
        _active_sessions.pop(token, None)
    return {"success": True, "detail": "Oturum kapatıldı."}


# ─── System & Telemetry Endpoints ────────────────────────

@app.get("/metrics", response_model=SystemMetrics)
async def get_metrics(_=Depends(verify_auth)):
    """Return current system-level CPU / RAM / Disk metrics."""
    return collect_system_metrics()


@app.get("/metrics/history")
async def api_metrics_history(range: str = "24h", _=Depends(verify_auth)):
    """Return 7-day, 3-day or 24-hour historical resource series."""
    valid_range = range if range in ("24h", "3d", "7d") else "24h"
    data = get_history(valid_range)
    return {"range": valid_range, "points": len(data), "data": data}


@app.get("/metrics/top-consumers")
async def api_top_consumers(range: str = "7d", _=Depends(verify_auth)):
    """Return top resource consuming processes ranked over the window."""
    valid_range = range if range in ("24h", "3d", "7d") else "7d"
    consumers = get_top_consumers(valid_range)
    return {"range": valid_range, "consumers": consumers}


@app.get("/health/matrix")
async def api_health_matrix(_=Depends(verify_auth)):
    """Return uptime, latency, and SSL certificate expiration for all infrastructure ports."""
    services = await probe_all_services(force=False)
    return {"timestamp": time.time(), "services": services}


# ─── Process Management Endpoints ────────────────────────

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


# ─── Live Log Streaming Endpoints ────────────────────────

@app.get("/projects/{project_id}/logs")
async def api_project_logs(project_id: str, _=Depends(verify_auth)):
    """Return recent static logs (last 80 lines) for a project."""
    project = get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    service_match = project.services[0].match if project.services else project_id
    try:
        res = subprocess.run(
            ["pm2", "logs", service_match, "--lines", "80", "--nostream"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=4
        )
        logs = res.stdout if res.stdout else "Log çıktısı bulunamadı."
    except Exception as e:
        logs = f"Log okunamadı: {e}"

    return {"project_id": project_id, "service": service_match, "logs": logs}


@app.get("/projects/{project_id}/logs/stream")
async def api_project_logs_stream(project_id: str, _=Depends(verify_auth)):
    """Stream real-time project logs using Server-Sent Events (SSE)."""
    project = get_project_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    service_match = project.services[0].match if project.services else project_id

    async def log_generator():
        yield f"data: 🚀 [{project.name}] Canlı log bağlantısı kuruldu. (Servis: {service_match})\n\n"
        proc = await asyncio.create_subprocess_exec(
            "pm2", "logs", service_match, "--raw", "--lines", "35",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                decoded = line.decode('utf-8', errors='replace').rstrip('\r\n')
                yield f"data: {decoded}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass

    return StreamingResponse(log_generator(), media_type="text/event-stream")
