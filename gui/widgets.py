"""
╔══════════════════════════════════════════════════════════╗
║      DustOps GUI — Custom Widgets (Dark Cyberpunk)       ║
║  Stat cards, progress bars, process table rows           ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import customtkinter as ctk
from typing import Callable

# ─── Color Palette ───────────────────────────────────────
BG_DEEP       = "#0A0A0F"
BG_CARD       = "#12121A"
BG_CARD_HOVER = "#1A1A28"
BG_INPUT      = "#16161F"
NEON_PURPLE   = "#9B59F5"
NEON_CYAN     = "#00F0FF"
NEON_PINK     = "#FF3B8B"
TEXT_PRIMARY   = "#E8E8F0"
TEXT_SECONDARY = "#8888A0"
TEXT_DIM       = "#55556A"
ALERT_RED      = "#FF3B3B"
SUCCESS_GREEN  = "#2ECC71"
BORDER_DIM     = "#2A2A3A"
PROGRESS_TRACK = "#1E1E2E"


# ─── Stat Card (CPU / RAM / Disk) ───────────────────────
class StatCard(ctk.CTkFrame):
    """
    A compact card showing:
      [icon]  LABEL
              VALUE
              ████████░░░░  68%
    """

    def __init__(
        self,
        master,
        label: str,
        icon: str = "◈",
        accent: str = NEON_PURPLE,
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_DIM,
            **kwargs,
        )
        self._accent = accent

        # Header
        self._header = ctk.CTkLabel(
            self,
            text=f" {icon}  {label}",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color=TEXT_SECONDARY,
            anchor="w",
        )
        self._header.pack(fill="x", padx=16, pady=(12, 0))

        # Value
        self._value_label = ctk.CTkLabel(
            self,
            text="—",
            font=ctk.CTkFont(family="Consolas", size=28, weight="bold"),
            text_color=TEXT_PRIMARY,
            anchor="w",
        )
        self._value_label.pack(fill="x", padx=16, pady=(2, 0))

        # Sub text
        self._sub_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_DIM,
            anchor="w",
        )
        self._sub_label.pack(fill="x", padx=16, pady=(0, 2))

        # Progress bar
        self._progress = ctk.CTkProgressBar(
            self,
            height=6,
            corner_radius=3,
            fg_color=PROGRESS_TRACK,
            progress_color=accent,
        )
        self._progress.pack(fill="x", padx=16, pady=(4, 14))
        self._progress.set(0)

    def update_value(
        self, value_text: str, percent: float, sub_text: str = ""
    ) -> None:
        """Update the card's displayed value and progress bar."""
        self._value_label.configure(text=value_text)
        self._sub_label.configure(text=sub_text)

        clamped = max(0.0, min(percent / 100.0, 1.0))
        self._progress.set(clamped)

        # Colour shift at high usage
        if percent > 90:
            self._progress.configure(progress_color=ALERT_RED)
        elif percent > 75:
            self._progress.configure(progress_color=NEON_PINK)
        else:
            self._progress.configure(progress_color=self._accent)


# ─── Process Row ────────────────────────────────────────
class ProcessRow(ctk.CTkFrame):
    """
    Single row in the process table:
      🟢  node   PID 1234   :3000   128 MB   4.2%   [Kill] [Restart]
    """

    def __init__(
        self,
        master,
        name: str,
        pid: int,
        port: int | None,
        ram_mb: float,
        cpu_pct: float,
        status: str,
        on_kill: Callable[[int], None] | None = None,
        on_restart: Callable[[str], None] | None = None,
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color=BG_CARD,
            corner_radius=8,
            height=42,
            **kwargs,
        )
        self.pack_propagate(False)

        font_mono = ctk.CTkFont(family="Consolas", size=12)
        font_mono_bold = ctk.CTkFont(family="Consolas", size=12, weight="bold")

        # Status indicator
        indicator = "●" if status == "running" else "○"
        color = NEON_CYAN if status == "running" else ALERT_RED
        ctk.CTkLabel(
            self, text=indicator, font=font_mono_bold,
            text_color=color, width=24,
        ).pack(side="left", padx=(12, 4))

        # Name
        ctk.CTkLabel(
            self, text=name, font=font_mono_bold,
            text_color=TEXT_PRIMARY, width=120, anchor="w",
        ).pack(side="left", padx=(0, 8))

        # PID
        ctk.CTkLabel(
            self, text=f"PID {pid}", font=font_mono,
            text_color=TEXT_SECONDARY, width=80, anchor="w",
        ).pack(side="left", padx=(0, 8))

        # Port
        port_text = f":{port}" if port else "—"
        ctk.CTkLabel(
            self, text=port_text, font=font_mono,
            text_color=NEON_PURPLE, width=60, anchor="w",
        ).pack(side="left", padx=(0, 8))

        # RAM
        ctk.CTkLabel(
            self, text=f"{ram_mb:.0f} MB", font=font_mono,
            text_color=TEXT_SECONDARY, width=70, anchor="e",
        ).pack(side="left", padx=(0, 8))

        # CPU
        ctk.CTkLabel(
            self, text=f"{cpu_pct:.1f}%", font=font_mono,
            text_color=TEXT_SECONDARY, width=55, anchor="e",
        ).pack(side="left", padx=(0, 12))

        # Kill button
        ctk.CTkButton(
            self,
            text="Kill",
            width=54,
            height=28,
            corner_radius=6,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            fg_color=ALERT_RED,
            hover_color="#CC2222",
            text_color="#FFFFFF",
            command=lambda: on_kill(pid) if on_kill else None,
        ).pack(side="right", padx=(0, 12))

        # Restart button
        ctk.CTkButton(
            self,
            text="Restart",
            width=66,
            height=28,
            corner_radius=6,
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            fg_color=NEON_PURPLE,
            hover_color="#7B3FD5",
            text_color="#FFFFFF",
            command=lambda: on_restart(name) if on_restart else None,
        ).pack(side="right", padx=(0, 6))


# ─── Status Bar ─────────────────────────────────────────
class StatusBar(ctk.CTkFrame):
    """Bottom status bar with connection indicator."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=BG_CARD,
            corner_radius=0,
            height=32,
            **kwargs,
        )
        self.pack_propagate(False)

        self._label = ctk.CTkLabel(
            self,
            text="◈ Connecting to Core Agent…",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color=TEXT_DIM,
            anchor="w",
        )
        self._label.pack(side="left", padx=16)

    def set_status(self, text: str, color: str = TEXT_DIM) -> None:
        self._label.configure(text=text, text_color=color)
