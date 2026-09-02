"""
╔══════════════════════════════════════════════════════════╗
║          DustOps Agent — Crash Watchdog                  ║
║  Background loop that detects process death instantly    ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import asyncio
import threading
import time
import logging
from datetime import datetime
from typing import Callable

import psutil

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from shared.models import CrashEvent, ProcessInfo
from agent.metrics import discover_tracked_processes

logger = logging.getLogger("dustops.watchdog")


class CrashWatchdog:
    """
    Continuously monitors tracked processes.

    Keeps a snapshot of previously seen PIDs. On each tick,
    any PID that was previously alive and is now gone triggers
    a CrashEvent dispatched to all registered callbacks.
    """

    def __init__(
        self,
        interval: int | None = None,
        on_crash: Callable[[CrashEvent], None] | None = None,
    ):
        self._interval = interval or config.WATCHDOG_INTERVAL
        self._callbacks: list[Callable[[CrashEvent], None]] = []
        if on_crash:
            self._callbacks.append(on_crash)

        # {pid: ProcessInfo} — last-known snapshot
        self._known: dict[int, ProcessInfo] = {}
        self._running = False
        self._thread: threading.Thread | None = None
        # async callbacks for discord bot integration
        self._async_callbacks: list[Callable[[CrashEvent], any]] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    # ── Callback Registration ────────────────────────────
    def on_crash(self, callback: Callable[[CrashEvent], None]) -> None:
        """Register a synchronous crash callback."""
        self._callbacks.append(callback)

    def on_crash_async(
        self,
        callback: Callable[[CrashEvent], any],
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Register an async crash callback with its event loop."""
        self._async_callbacks.append(callback)
        self._loop = loop

    # ── Core Loop ────────────────────────────────────────
    def _tick(self) -> None:
        """Single watchdog tick — compare current vs. known."""
        current_procs = discover_tracked_processes()
        current_pids = {p.pid for p in current_procs}
        current_map = {p.pid: p for p in current_procs}

        # Detect processes that vanished
        for pid, info in list(self._known.items()):
            if pid not in current_pids:
                # Ignore short-lived processes (uptime < 30 seconds)
                if time.time() - info.create_time < 30:
                    continue
                
                # Confirm it's truly dead (not just renamed/re-PID'd)
                if not psutil.pid_exists(pid):
                    event = CrashEvent(
                        service_name=info.name,
                        pid=pid,
                        exit_code=None,
                        timestamp=datetime.utcnow(),
                        message=f"Process '{info.name}' (PID {pid}) exited unexpectedly.",
                    )
                    logger.warning(
                        "CRASH DETECTED: %s (PID %d)", info.name, pid
                    )
                    self._dispatch(event)

        # Update snapshot
        self._known = current_map

    def _dispatch(self, event: CrashEvent) -> None:
        """Dispatch crash event to all registered callbacks."""
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception:
                logger.exception("Sync crash callback failed")

        for acb in self._async_callbacks:
            if self._loop and not self._loop.is_closed():
                asyncio.run_coroutine_threadsafe(acb(event), self._loop)

    def _run_loop(self) -> None:
        """Blocking loop executed in the watchdog thread."""
        logger.info(
            "Watchdog started — polling every %ds", self._interval
        )
        # Initial snapshot (no crash alerts on first pass)
        self._known = {
            p.pid: p for p in discover_tracked_processes()
        }
        while self._running:
            time.sleep(self._interval)
            if self._running:
                try:
                    self._tick()
                except Exception:
                    logger.exception("Watchdog tick error")

    # ── Lifecycle ────────────────────────────────────────
    def start(self) -> None:
        """Start the watchdog in a background daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="dustops-watchdog"
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the watchdog to stop."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self._interval + 2)

    @property
    def known_processes(self) -> dict[int, ProcessInfo]:
        """Return the last-known process snapshot (thread-safe read)."""
        return dict(self._known)
