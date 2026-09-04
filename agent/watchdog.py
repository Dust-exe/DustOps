"""
╔══════════════════════════════════════════════════════════╗
║          DustOps Agent — Crash & Auto-Healer Watchdog    ║
║  Background loop that detects process death & RAM leaks  ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import asyncio
import threading
import time
import logging
import subprocess
from datetime import datetime, timezone
from typing import Callable

import psutil

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from shared.models import CrashEvent, ProcessInfo
from agent.metrics import discover_tracked_processes
from agent.history_recorder import record_snapshot

logger = logging.getLogger("dustops.watchdog")

MAX_MEMORY_THRESHOLD_MB = getattr(config, "MAX_PROCESS_MEMORY_MB", 250.0)
MEMORY_CONSECUTIVE_LIMIT = 3  # 3 consecutive violations (approx 1.5 - 2 minutes)


class CrashWatchdog:
    """
    Continuously monitors tracked processes for both unexpected exits (crashes)
    and severe memory leaks (Auto-Healer).
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
        # {pid: count_of_consecutive_breaches}
        self._memory_violations: dict[int, int] = {}
        # Counter for periodic telemetry snapshot recording (every 5 mins)
        self._tick_counter = 0

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
        """Single watchdog tick — compare current vs. known, inspect RAM leaks."""
        self._tick_counter += 1
        # Record 5-minute periodic telemetry snapshot (every 10 ticks @ 30s)
        if self._tick_counter >= 10:
            self._tick_counter = 0
            try:
                record_snapshot()
            except Exception as e:
                logger.warning("History snapshot failed in watchdog: %s", e)

        current_procs = discover_tracked_processes()
        current_pids = {p.pid for p in current_procs}
        current_map = {p.pid: p for p in current_procs}

        # 1. Detect processes that vanished (Crashes)
        for pid, info in list(self._known.items()):
            if pid not in current_pids:
                # Clean up memory violation tracker
                self._memory_violations.pop(pid, None)

                # Ignore short-lived processes (uptime < 30 seconds)
                if time.time() - info.create_time < 30:
                    continue
                
                # Confirm it's truly dead (not just renamed/re-PID'd)
                if not psutil.pid_exists(pid):
                    event = CrashEvent(
                        service_name=info.name,
                        pid=pid,
                        exit_code=None,
                        timestamp=datetime.now(timezone.utc),
                        message=f"Process '{info.name}' (PID {pid}) beklenmedik şekilde kapandı.",
                    )
                    logger.warning("CRASH DETECTED: %s (PID %d)", info.name, pid)
                    self._dispatch(event)

        # 2. Auto-Healer: Detect sustained memory leaks
        for p in current_procs:
            # Skip ide-server or known high-memory infrastructure tools
            if any(skip in p.name.lower() for skip in ("tsserver", "remote-cli", "vscode", "antigravity")):
                continue

            if p.memory_mb > MAX_MEMORY_THRESHOLD_MB:
                self._memory_violations[p.pid] = self._memory_violations.get(p.pid, 0) + 1
                logger.warning(
                    "High memory detected for %s (PID %d): %.1f MB (Violation %d/%d)",
                    p.name, p.pid, p.memory_mb, self._memory_violations[p.pid], MEMORY_CONSECUTIVE_LIMIT
                )

                if self._memory_violations[p.pid] >= MEMORY_CONSECUTIVE_LIMIT:
                    self._memory_violations[p.pid] = 0
                    self._auto_heal_process(p)
            else:
                self._memory_violations.pop(p.pid, None)

        # Update snapshot
        self._known = current_map

    def _auto_heal_process(self, proc: ProcessInfo) -> None:
        """Trigger an automated soft restart to heal memory leaks."""
        logger.warning(
            "AUTO-HEAL TRIGGERED: Process %s (PID %d) exceeded %.1fMB RAM limit.",
            proc.name, proc.pid, MAX_MEMORY_THRESHOLD_MB
        )

        restart_cmd = None
        # Try to identify PM2 service name
        try:
            from agent.process_manager import list_registered_services
            services = list_registered_services()
            for s in services:
                if s.lower() in proc.name.lower() or proc.name.lower() in s.lower():
                    restart_cmd = f"pm2 restart {s}"
                    break
        except Exception:
            pass

        if not restart_cmd and "python" in proc.name.lower():
            if "run_agent" in proc.cmdline:
                restart_cmd = "pm2 restart dustops-agent"
            elif "run_bot" in proc.cmdline:
                restart_cmd = "pm2 restart dustops-bot"

        if restart_cmd:
            try:
                logger.info("Executing auto-heal command: %s", restart_cmd)
                subprocess.run(restart_cmd, shell=True, timeout=15, check=False)
            except Exception as e:
                logger.error("Auto-heal restart failed: %s", e)

        # Dispatch alert to Discord bot and event buffer
        event = CrashEvent(
            service_name=f"🛡️ Auto-Healer: {proc.name}",
            pid=proc.pid,
            exit_code=0,
            timestamp=datetime.now(timezone.utc),
            message=(
                f"🛡️ [Auto-Healer] '{proc.name}' süreci {proc.memory_mb:.1f}MB RAM tüketerek "
                f"{MAX_MEMORY_THRESHOLD_MB:.0f}MB sınırını aştı. Bellek temizliği için otomatik yeniden başlatıldı."
            )
        )
        self._dispatch(event)

    def _dispatch(self, event: CrashEvent) -> None:
        """Dispatch crash/heal event to all registered callbacks."""
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
        logger.info("Watchdog started — polling every %ds (Memory limit: %.0f MB)", self._interval, MAX_MEMORY_THRESHOLD_MB)
        # Initial snapshot
        self._known = {p.pid: p for p in discover_tracked_processes()}
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
