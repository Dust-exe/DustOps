"""
╔══════════════════════════════════════════════════════════╗
║             DustOps — Centralized Configuration          ║
║         Loads .env and exposes typed settings             ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# ─── Load .env from project root ────────────────────────
_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _env_int(key: str, default: int = 0) -> int:
    raw = _env(key)
    return int(raw) if raw.isdigit() else default


def _env_list(key: str, default: str = "") -> list[str]:
    raw = _env(key, default)
    return [tok.strip() for tok in raw.split(",") if tok.strip()]


# ── Discord ──────────────────────────────────────────────
DISCORD_TOKEN: str = _env("DISCORD_TOKEN")
OWNER_USER_ID: int = _env_int("OWNER_USER_ID")

# ── Core Agent API ───────────────────────────────────────
API_HOST: str = _env("API_HOST", "127.0.0.1")
API_PORT: int = _env_int("API_PORT", 4141)
API_BASE_URL: str = f"http://{API_HOST}:{API_PORT}"

# ── Watchdog ─────────────────────────────────────────────
WATCH_KEYWORDS: list[str] = _env_list("WATCH_KEYWORDS", "node,python,vite,uvicorn")
WATCH_PORTS: list[int] = [int(p) for p in _env_list("WATCH_PORTS", "3000,5173,8000,8080")]
WATCHDOG_INTERVAL: int = _env_int("WATCHDOG_INTERVAL", 5)

# ── Dashboard ────────────────────────────────────────────
DASHBOARD_INTERVAL: int = _env_int("DASHBOARD_INTERVAL", 3600)

# ── Web UI ───────────────────────────────────────────────
WEB_USERNAME: str = _env("WEB_USERNAME", "admin")
WEB_PASSWORD: str = _env("WEB_PASSWORD", "123456")
