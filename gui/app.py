"""
╔══════════════════════════════════════════════════════════╗
║       DustOps GUI — Main Application Window              ║
║   Dark cyberpunk control panel • customtkinter           ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import sys
import os
import logging
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gui.widgets import (
    StatCard, ProcessRow, StatusBar,
    BG_DEEP, BG_CARD, NEON_PURPLE, NEON_CYAN, NEON_PINK,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_DIM, BORDER_DIM,
    SUCCESS_GREEN, ALERT_RED,
)
from gui.api_client import AgentAPIClient
from shared.models import SystemMetrics, ProcessInfo, ActionResult

logger = logging.getLogger("dustops.gui")

# Poll interval in ms
POLL_INTERVAL = 3000


class DustOpsApp(ctk.CTk):
    """
    Main application window.

    Layout:
    ┌──────────────────────────────────────────────┐
    │  ◈ DustOps Control Panel          [Refresh]  │
    ├───────────┬───────────┬──────────────────────│
    │  CPU Card │  RAM Card │     Disk Card        │
    ├───────────┴───────────┴──────────────────────│
    │  ◈ Tracked Processes                         │
    │  ┌──────────────────────────────────────────┐│
    │  │ Row 1 ...  [Kill] [Restart]              ││
    │  │ Row 2 ...                                ││
    │  │ ...                                      ││
    │  └──────────────────────────────────────────┘│
    ├──────────────────────────────────────────────│
    │  ◈ Connected • 19:44 UTC                     │
    └──────────────────────────────────────────────┘
    """

    def __init__(self):
        super().__init__()

        # ── Window Setup ─────────────────────────────────
        self.title("DustOps — Control Panel")
        self.geometry("820x640")
        self.minsize(720, 520)
        self.configure(fg_color=BG_DEEP)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self._api = AgentAPIClient()
        self._process_rows: list[ProcessRow] = []

        self._build_ui()
        self._start_polling()

    # ─── Build UI ────────────────────────────────────────
    def _build_ui(self) -> None:
        # ── Title Bar ────────────────────────────────────
        title_frame = ctk.CTkFrame(self, fg_color=BG_DEEP, corner_radius=0)
        title_frame.pack(fill="x", padx=20, pady=(16, 0))

        ctk.CTkLabel(
            title_frame,
            text="◈  DustOps",
            font=ctk.CTkFont(family="Consolas", size=22, weight="bold"),
            text_color=NEON_PURPLE,
        ).pack(side="left")

        ctk.CTkLabel(
            title_frame,
            text="  Control Panel",
            font=ctk.CTkFont(family="Consolas", size=22),
            text_color=TEXT_DIM,
        ).pack(side="left")

        self._btn_refresh = ctk.CTkButton(
            title_frame,
            text="⟳  Refresh",
            width=100,
            height=32,
            corner_radius=8,
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            fg_color=NEON_PURPLE,
            hover_color="#7B3FD5",
            command=self._poll_now,
        )
        self._btn_refresh.pack(side="right")

        # ── Stat Cards Row ───────────────────────────────
        cards_frame = ctk.CTkFrame(self, fg_color=BG_DEEP, corner_radius=0)
        cards_frame.pack(fill="x", padx=20, pady=(16, 0))
        cards_frame.columnconfigure((0, 1, 2), weight=1, uniform="card")

        self._cpu_card = StatCard(
            cards_frame, label="CPU USAGE", icon="🧠", accent=NEON_CYAN
        )
        self._cpu_card.grid(row=0, column=0, padx=(0, 6), sticky="nsew")

        self._ram_card = StatCard(
            cards_frame, label="RAM USAGE", icon="💾", accent=NEON_PURPLE
        )
        self._ram_card.grid(row=0, column=1, padx=6, sticky="nsew")

        self._disk_card = StatCard(
            cards_frame, label="DISK USAGE", icon="💿", accent=NEON_PINK
        )
        self._disk_card.grid(row=0, column=2, padx=(6, 0), sticky="nsew")

        # ── Process Section Header ───────────────────────
        proc_header = ctk.CTkFrame(self, fg_color=BG_DEEP, corner_radius=0)
        proc_header.pack(fill="x", padx=20, pady=(20, 0))

        ctk.CTkLabel(
            proc_header,
            text="◈  Tracked Processes",
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

        self._proc_count_label = ctk.CTkLabel(
            proc_header,
            text="0 processes",
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color=TEXT_DIM,
        )
        self._proc_count_label.pack(side="right")

        # ── Column Headers ───────────────────────────────
        col_frame = ctk.CTkFrame(self, fg_color=BG_DEEP, corner_radius=0, height=24)
        col_frame.pack(fill="x", padx=20, pady=(8, 0))
        col_frame.pack_propagate(False)

        font_hdr = ctk.CTkFont(family="Consolas", size=10, weight="bold")
        headers = [
            ("", 36), ("NAME", 120), ("PID", 80), ("PORT", 60),
            ("RAM", 70), ("CPU", 55),
        ]
        for text, width in headers:
            ctk.CTkLabel(
                col_frame, text=text, font=font_hdr,
                text_color=TEXT_DIM, width=width, anchor="w",
            ).pack(side="left", padx=(0, 8) if text != "" else (12, 4))

        # ── Scrollable Process List ──────────────────────
        self._proc_scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=BG_DEEP,
            corner_radius=8,
            border_width=1,
            border_color=BORDER_DIM,
            scrollbar_button_color=NEON_PURPLE,
            scrollbar_button_hover_color="#7B3FD5",
        )
        self._proc_scroll.pack(fill="both", expand=True, padx=20, pady=(4, 0))

        # ── Status Bar ───────────────────────────────────
        self._status_bar = StatusBar(self)
        self._status_bar.pack(fill="x", side="bottom")

    # ─── Polling ─────────────────────────────────────────
    def _start_polling(self) -> None:
        """Begin periodic polling of the Core Agent API."""
        self._poll_now()

    def _poll_now(self) -> None:
        """Trigger a single poll cycle."""
        self._api.fetch_metrics(
            on_success=self._on_metrics,
            on_error=self._on_api_error,
        )
        self._api.fetch_processes(
            on_success=self._on_processes,
            on_error=self._on_api_error,
        )

        # Schedule next poll
        self.after(POLL_INTERVAL, self._poll_now)

    # ─── Callbacks (called from background threads) ─────
    def _on_metrics(self, metrics: SystemMetrics) -> None:
        """Update stat cards — must schedule onto main thread."""
        self.after(0, self._apply_metrics, metrics)

    def _on_processes(self, processes: list[ProcessInfo]) -> None:
        """Update process list — must schedule onto main thread."""
        self.after(0, self._apply_processes, processes)

    def _on_api_error(self, err: str) -> None:
        self.after(
            0,
            self._status_bar.set_status,
            f"✗  {err}",
            ALERT_RED,
        )

    # ─── Apply Data (Main Thread) ────────────────────────
    def _apply_metrics(self, m: SystemMetrics) -> None:
        self._cpu_card.update_value(
            f"{m.cpu_percent:.1f}%", m.cpu_percent,
        )
        self._ram_card.update_value(
            f"{m.ram_used_mb:.0f} MB",
            m.ram_percent,
            f"/ {m.ram_total_mb:.0f} MB total",
        )
        self._disk_card.update_value(
            f"{m.disk_used_gb:.1f} GB",
            m.disk_percent,
            f"/ {m.disk_total_gb:.1f} GB total",
        )

        now = datetime.utcnow().strftime("%H:%M:%S UTC")
        self._status_bar.set_status(
            f"◈  Connected to Core Agent  •  {now}",
            SUCCESS_GREEN,
        )

    def _apply_processes(self, procs: list[ProcessInfo]) -> None:
        # Clear old rows
        for row in self._process_rows:
            row.destroy()
        self._process_rows.clear()

        self._proc_count_label.configure(text=f"{len(procs)} processes")

        for p in procs:
            row = ProcessRow(
                self._proc_scroll,
                name=p.name,
                pid=p.pid,
                port=p.port,
                ram_mb=p.ram_mb,
                cpu_pct=p.cpu_percent,
                status=p.status,
                on_kill=self._handle_kill,
                on_restart=self._handle_restart,
            )
            row.pack(fill="x", pady=(0, 4))
            self._process_rows.append(row)

    # ─── Action Handlers ────────────────────────────────
    def _handle_kill(self, pid: int) -> None:
        confirm = messagebox.askyesno(
            "DustOps — Kill Process",
            f"Are you sure you want to kill PID {pid}?",
        )
        if not confirm:
            return

        self._api.kill_process(
            pid,
            on_success=lambda r: self.after(
                0,
                self._status_bar.set_status,
                f"✓  {r.detail}",
                SUCCESS_GREEN,
            ),
            on_error=lambda e: self.after(
                0,
                self._status_bar.set_status,
                f"✗  Kill failed: {e}",
                ALERT_RED,
            ),
        )

    def _handle_restart(self, name: str) -> None:
        confirm = messagebox.askyesno(
            "DustOps — Restart Service",
            f"Restart service '{name}'?",
        )
        if not confirm:
            return

        self._api.restart_service(
            name,
            on_success=lambda r: self.after(
                0,
                self._status_bar.set_status,
                f"🚀  {r.detail}",
                SUCCESS_GREEN,
            ),
            on_error=lambda e: self.after(
                0,
                self._status_bar.set_status,
                f"✗  Restart failed: {e}",
                ALERT_RED,
            ),
        )
