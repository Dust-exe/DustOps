"""
╔══════════════════════════════════════════════════════════╗
║       DustOps GUI — Async HTTP Client for Core Agent     ║
║    Non-blocking API calls from the GUI thread            ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import threading
import logging
from typing import Callable, Any

import httpx

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from shared.models import SystemMetrics, ProcessInfo, ActionResult

logger = logging.getLogger("dustops.gui.api")
API = config.API_BASE_URL


class AgentAPIClient:
    """
    Thread-safe HTTP client that calls the Core Agent API
    in a background thread and delivers results back via callbacks,
    preventing GUI freezes.
    """

    def __init__(self):
        self._base = API

    def _request(
        self,
        method: str,
        path: str,
        callback: Callable[[Any], None] | None = None,
        error_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Execute an HTTP request in a background thread."""

        def _worker():
            try:
                with httpx.Client(timeout=10) as http:
                    if method == "GET":
                        resp = http.get(f"{self._base}{path}")
                    else:
                        resp = http.post(f"{self._base}{path}")

                    if resp.status_code == 200:
                        if callback:
                            callback(resp.json())
                    else:
                        detail = resp.json().get("detail", resp.text)
                        if error_callback:
                            error_callback(f"HTTP {resp.status_code}: {detail}")
            except httpx.ConnectError:
                if error_callback:
                    error_callback("Agent unreachable — is it running?")
            except Exception as exc:
                logger.exception("API request error")
                if error_callback:
                    error_callback(str(exc))

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    # ── Typed Accessors ──────────────────────────────────
    def fetch_metrics(
        self,
        on_success: Callable[[SystemMetrics], None],
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        def _parse(data):
            on_success(SystemMetrics(**data))

        self._request("GET", "/metrics", _parse, on_error)

    def fetch_processes(
        self,
        on_success: Callable[[list[ProcessInfo]], None],
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        def _parse(data):
            on_success([ProcessInfo(**p) for p in data])

        self._request("GET", "/processes", _parse, on_error)

    def fetch_services(
        self,
        on_success: Callable[[list[str]], None],
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._request("GET", "/services", on_success, on_error)

    def kill_process(
        self,
        pid: int,
        on_success: Callable[[ActionResult], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        def _parse(data):
            if on_success:
                on_success(ActionResult(**data))

        self._request("POST", f"/kill/{pid}", _parse, on_error)

    def restart_service(
        self,
        name: str,
        on_success: Callable[[ActionResult], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        def _parse(data):
            if on_success:
                on_success(ActionResult(**data))

        self._request("POST", f"/restart/{name}", _parse, on_error)

    def check_health(
        self,
        on_success: Callable[[dict], None],
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._request("GET", "/health", on_success, on_error)
