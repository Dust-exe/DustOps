"""
╔══════════════════════════════════════════════════════════╗
║       DustOps Bot — Crash Alert Embeds                   ║
║       High-priority red alerts sent to owner DM          ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import discord
from datetime import datetime

from shared.models import CrashEvent
from shared.constants import Colors, Emoji


def build_crash_alert_embed(event: CrashEvent) -> discord.Embed:
    if event.pid == 0 and "GÜVENLİK İHLALİ" in event.service_name:
        embed = discord.Embed(
            title="🚨 GÜVENLİK İHLALİ",
            description=event.message,
            color=0xFF0000,
            timestamp=event.timestamp,
        )
        embed.set_footer(text="DustOps Security System")
        return embed

    embed = discord.Embed(
        title=f"CRASH DETECTED: {event.service_name}",
        color=Colors.ALERT_RED,
        timestamp=event.timestamp,
    )

    embed.add_field(
        name="Details",
        value=(
            f"**Service:** {event.service_name}\n"
            f"**PID:** {event.pid}\n"
            f"**Time:** {event.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"{'**Exit Code:** ' + str(event.exit_code) if event.exit_code is not None else ''}\n\n"
            f"{event.message}"
        ),
        inline=False,
    )

    embed.set_footer(
        text="DustOps Crash Watchdog • Immediate Alert",
    )

    return embed
