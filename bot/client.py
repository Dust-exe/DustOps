"""
╔══════════════════════════════════════════════════════════╗
║       DustOps Bot — Discord Client (Owner-Only DM)       ║
║  Hourly auto-updating dashboard + crash alert consumer   ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import discord
from discord.ext import tasks
import httpx

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from shared.models import SystemMetrics, ProcessInfo, CrashEvent, ProjectStatus
from bot.dashboard import build_dashboard_embed
from bot.alerts import build_crash_alert_embed
from bot.views import DashboardView

logger = logging.getLogger("dustops.bot")
API = config.API_BASE_URL


class DustOpsBot(discord.Client):
    """
    Owner-only DM bot.

    • Sends / edits a single dashboard embed to the owner DM.
    • Polls the Core Agent for crash events and sends immediate alerts.
    • Registers persistent interactive views.
    """

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = False
        super().__init__(intents=intents)

        # ID of the dashboard message in owner DM (edit, don't spam)
        self._dashboard_msg_id: int | None = None
        self._owner_dm: discord.DMChannel | None = None
        self._http = httpx.AsyncClient(
            timeout=15,
            auth=(getattr(config, "WEB_USERNAME", ""), getattr(config, "WEB_PASSWORD", ""))
        )

    # ── Lifecycle ────────────────────────────────────────
    async def setup_hook(self):
        """Called before the bot connects — register persistent views."""
        self.add_view(DashboardView())

    async def on_ready(self):
        logger.info("Bot online: %s", self.user)
        print()
        print("╔══════════════════════════════════════════════════╗")
        print("║     ◈ DustOps Discord Bot — Online ◈            ║")
        print(f"║  Bot: {str(self.user).ljust(42)}║")
        print(f"║  Owner: {str(config.OWNER_USER_ID).ljust(40)}║")
        print("╚══════════════════════════════════════════════════╝")
        print()

        # Open DM channel with owner
        try:
            owner = await self.fetch_user(config.OWNER_USER_ID)
            self._owner_dm = await owner.create_dm()
            logger.info("Owner DM channel opened: %s", owner)
        except Exception:
            logger.exception("Failed to open owner DM channel")
            return

        # Start background loops
        if not self.dashboard_loop.is_running():
            self.dashboard_loop.start()
        if not self.crash_poll_loop.is_running():
            self.crash_poll_loop.start()

    async def close(self):
        await self._http.aclose()
        await super().close()

    # ── Dashboard Loop (hourly, edits existing message) ──
    @tasks.loop(seconds=config.DASHBOARD_INTERVAL)
    async def dashboard_loop(self):
        """Send or edit the dashboard embed in owner DM."""
        if not self._owner_dm:
            return

        try:
            m_resp = await self._http.get(f"{API}/metrics")
            p_resp = await self._http.get(f"{API}/projects")

            metrics = SystemMetrics(**m_resp.json())
            projects = [ProjectStatus(**p) for p in p_resp.json()]
            embed = build_dashboard_embed(metrics, projects)
            view = DashboardView(projects)

            if self._dashboard_msg_id:
                # Try to edit existing message
                try:
                    msg = await self._owner_dm.fetch_message(
                        self._dashboard_msg_id
                    )
                    await msg.edit(embed=embed, view=view)
                    logger.info("Dashboard embed updated (edit)")
                    return
                except discord.NotFound:
                    logger.warning(
                        "Dashboard message deleted, sending new one"
                    )
                    self._dashboard_msg_id = None

            # Send new dashboard message
            msg = await self._owner_dm.send(embed=embed, view=view)
            self._dashboard_msg_id = msg.id
            logger.info("Dashboard embed sent (new, id=%d)", msg.id)

        except httpx.ConnectError:
            logger.warning(
                "Core Agent unreachable at %s — skipping dashboard update",
                API,
            )
        except Exception:
            logger.exception("Dashboard update failed")

    @dashboard_loop.before_loop
    async def _before_dashboard(self):
        await self.wait_until_ready()
        # Send immediately on first launch, then wait interval
        await asyncio.sleep(2)

    # ── Crash Event Polling ──────────────────────────────
    @tasks.loop(seconds=10)
    async def crash_poll_loop(self):
        """Poll the Core Agent /crashes endpoint and alert owner."""
        if not self._owner_dm:
            return

        try:
            resp = await self._http.get(f"{API}/crashes")
            if resp.status_code != 200:
                return

            events = resp.json()
            for ev_data in events:
                event = CrashEvent(**ev_data)
                embed = build_crash_alert_embed(event)
                await self._owner_dm.send(embed=embed)
                logger.warning(
                    "Crash alert sent to owner: %s", event.service_name
                )
        except httpx.ConnectError:
            pass  # Agent not running, silently skip
        except Exception:
            logger.exception("Crash poll error")

    @crash_poll_loop.before_loop
    async def _before_crash_poll(self):
        await self.wait_until_ready()
        await asyncio.sleep(5)
