"""
╔══════════════════════════════════════════════════════════╗
║       DustOps Bot — Dashboard Embed Builder              ║
║   Builds grouped project & system resource rich embed    ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import discord
from datetime import datetime

from shared.models import SystemMetrics, ProjectStatus
from shared.constants import Colors


def _bar(percent: float, length: int = 14) -> str:
    """Render a text-based progress bar."""
    filled = int(percent / 100 * length)
    return f"`{'█' * filled}{'░' * (length - filled)}` **{percent:.1f}%**"


def build_dashboard_embed(
    metrics: SystemMetrics,
    projects: list[ProjectStatus],
) -> discord.Embed:
    """
    Build an embed containing system metrics and project-grouped services.
    """
    embed = discord.Embed(
        title="DustOps — Infrastructure Control Panel",
        color=Colors.NEON_PURPLE,
        timestamp=datetime.utcnow(),
    )

    # ── System Resources ─────────────────────────────────
    metrics_text = (
        f"**CPU** {_bar(metrics.cpu_percent)}\n"
        f"**RAM** {_bar(metrics.ram_percent)} (`{metrics.ram_used_mb:.0f}` / `{metrics.ram_total_mb:.0f}` MB)\n"
        f"**Disk** {_bar(metrics.disk_percent)} (`{metrics.disk_used_gb:.1f}` / `{metrics.disk_total_gb:.1f}` GB)"
    )
    embed.add_field(
        name="System Resources",
        value=metrics_text,
        inline=False,
    )

    # ── Projects & Scoped Services ───────────────────────
    if not projects:
        embed.add_field(
            name="Projects",
            value="No projects registered or agent offline.",
            inline=False,
        )
    else:
        for proj in projects:
            lines: list[str] = []
            service_count = len(proj.services)
            for idx, s in enumerate(proj.services):
                branch = "└─" if idx == service_count - 1 else "├─"
                icon = "🟢" if s.status == "running" else "🔴"
                
                if s.process:
                    pid_str = f"PID: {s.process.pid}"
                    port_str = f":{s.process.port}" if s.process.port else "-"
                    ram_str = f"{s.process.ram_mb:.1f} MB"
                    cpu_str = f"{s.process.cpu_percent:.1f}%"
                    lines.append(
                        f"`{branch}` {icon} **{s.name}** | `{pid_str}` | `{port_str}` | `{ram_str}` | `{cpu_str}`"
                    )
                else:
                    port_str = f":{s.port}" if s.port else "-"
                    lines.append(
                        f"`{branch}` {icon} **{s.name}** | `STOPPED` | `{port_str}`"
                    )

            body = "\n".join(lines) if lines else "*No services configured.*"
            health_badge = "✅" if proj.is_healthy else "⚠️"
            embed.add_field(
                name=f"{proj.name} `{proj.id}` {health_badge}",
                value=body,
                inline=False,
            )

    embed.set_footer(
        text="DustOps • Scoped Infrastructure Management",
        icon_url="https://cdn.discordapp.com/embed/avatars/0.png",
    )

    return embed
