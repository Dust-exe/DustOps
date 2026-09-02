"""
╔══════════════════════════════════════════════════════════╗
║      DustOps Bot — Interactive Discord Views             ║
║  Grouped Project Controls, Scoped Exec Modal & Restarts  ║
║  ALL interactions verify OWNER_USER_ID                   ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import logging
import discord
from discord.ui import View, Button, Select, button
import httpx

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from shared.models import SystemMetrics, ProjectStatus

logger = logging.getLogger("dustops.views")
API = config.API_BASE_URL


def _owner_only(interaction: discord.Interaction) -> bool:
    """Return True if the interacting user is the owner."""
    return interaction.user.id == config.OWNER_USER_ID


# ─── Scoped Command Exec Modal ──────────────────────────
class ExecCommandModal(discord.ui.Modal):
    """Modal that takes a project id and shell command to execute in project cwd."""

    def __init__(self, default_project: str = "dust-studio"):
        super().__init__(title="⚡ Proje Dizininde Komut Çalıştır")
        self.project_input = discord.ui.TextInput(
            label="Proje ID",
            placeholder="örn: dust-studio, dustops, arac-galeri, dust-analyz",
            default=default_project,
            required=True,
            max_length=50,
        )
        self.cmd_input = discord.ui.TextInput(
            label="Çalıştırılacak Shell Komutu",
            placeholder="örn: git status veya npm run build veya pm2 status",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=500,
        )
        self.add_item(self.project_input)
        self.add_item(self.cmd_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not _owner_only(interaction):
            await interaction.response.send_message("⛔ Yetkisiz işlem.", ephemeral=True)
            return

        proj_id = self.project_input.value.strip()
        cmd = self.cmd_input.value.strip()

        await interaction.response.defer(ephemeral=True)

        async with httpx.AsyncClient(
            timeout=35,
            auth=(getattr(config, "WEB_USERNAME", ""), getattr(config, "WEB_PASSWORD", ""))
        ) as http:
            try:
                resp = await http.post(
                    f"{API}/projects/{proj_id}/exec",
                    json={"command": cmd}
                )
                if resp.status_code != 200:
                    data = resp.json()
                    await interaction.followup.send(
                        f"❌ **Hata ({resp.status_code}):** {data.get('detail', 'Bilinmeyen hata')}",
                        ephemeral=True
                    )
                    return

                res = resp.json()
                stdout = res.get("stdout", "")
                stderr = res.get("stderr", "")
                error = res.get("error")

                combined_out = stdout if stdout else ""
                if stderr:
                    combined_out += f"\n[STDERR]\n{stderr}"
                if error:
                    combined_out += f"\n[HATA]\n{error}"

                if not combined_out.strip():
                    combined_out = "[Çıktı yok - Komut başarıyla tamamlandı]"

                # User requirement: slice last 1800 chars in bash code block
                sliced_output = combined_out[-1800:] if len(combined_out) > 1800 else combined_out
                exit_code_str = f"Exit Code: {res.get('exit_code')}"

                reply = (
                    f"📂 **Proje:** `{proj_id}` (`{res.get('cwd', '')}`)\n"
                    f"⚡ **Komut:** `{cmd}` | `{exit_code_str}`\n"
                    f"```bash\n{sliced_output}\n```"
                )
                await interaction.followup.send(reply, ephemeral=True)
            except Exception as exc:
                await interaction.followup.send(f"❌ API Bağlantı Hatası: {exc}", ephemeral=True)


# ─── Kill Process Modal ─────────────────────────────────
class KillModal(discord.ui.Modal, title="🛑 Süreç Sonlandır (Kill PID)"):
    """Modal that asks for a PID to kill."""

    pid_input = discord.ui.TextInput(
        label="Süreç PID",
        placeholder="örn: 12345",
        required=True,
        max_length=10,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not _owner_only(interaction):
            await interaction.response.send_message("⛔ Yetkisiz işlem.", ephemeral=True)
            return

        pid = self.pid_input.value.strip()
        if not pid.isdigit():
            await interaction.response.send_message("❌ Geçersiz PID.", ephemeral=True)
            return

        async with httpx.AsyncClient(
            timeout=10,
            auth=(getattr(config, "WEB_USERNAME", ""), getattr(config, "WEB_PASSWORD", ""))
        ) as http:
            try:
                resp = await http.post(f"{API}/kill/{pid}")
                data = resp.json()
                if resp.status_code == 200:
                    await interaction.response.send_message(
                        f"✅ **Sonlandırıldı:** {data.get('detail', 'Tamam')}",
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        f"❌ {data.get('detail', 'Başarısız')}",
                        ephemeral=True,
                    )
            except Exception as exc:
                await interaction.response.send_message(
                    f"❌ API Hatası: {exc}", ephemeral=True
                )


# ─── Restart Project Select ─────────────────────────────
class ProjectRestartSelect(Select):
    """Dropdown for quick restart of a configured project."""

    def __init__(self, projects: list[ProjectStatus] | None = None):
        options = []
        if projects:
            for p in projects[:25]:
                options.append(
                    discord.SelectOption(
                        label=f"{p.name[:25]}",
                        value=p.id,
                        description=f"Dizin: {p.cwd[-40:]}",
                        emoji="🔄"
                    )
                )
        if not options:
            options = [
                discord.SelectOption(label="dust-studio", value="dust-studio", emoji="🌐"),
                discord.SelectOption(label="dust-studio-kayit", value="dust-studio-kayit", emoji="🤖"),
                discord.SelectOption(label="dust-analyz", value="dust-analyz", emoji="📊"),
                discord.SelectOption(label="arac-galeri", value="arac-galeri", emoji="🚗"),
                discord.SelectOption(label="dustops", value="dustops", emoji="🛡️"),
            ]

        super().__init__(
            placeholder="🔄 Yeniden Başlatılacak Projeyi Seç...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="dustops:select_restart_project",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if not _owner_only(interaction):
            await interaction.response.send_message("⛔ Yetkisiz işlem.", ephemeral=True)
            return

        project_id = self.values[0]
        await interaction.response.defer(ephemeral=True)

        async with httpx.AsyncClient(
            timeout=35,
            auth=(getattr(config, "WEB_USERNAME", ""), getattr(config, "WEB_PASSWORD", ""))
        ) as http:
            try:
                resp = await http.post(f"{API}/projects/{project_id}/restart")
                data = resp.json()
                if resp.status_code == 200:
                    await interaction.followup.send(
                        f"🚀 **Proje Yeniden Başlatıldı (`{project_id}`):** {data.get('detail', 'Tamam')}",
                        ephemeral=True,
                    )
                else:
                    await interaction.followup.send(
                        f"❌ **Yeniden Başlatma Hatası:** {data.get('detail', 'Başarısız')}",
                        ephemeral=True,
                    )
            except Exception as exc:
                await interaction.followup.send(f"❌ API Hatası: {exc}", ephemeral=True)


# ─── Dashboard View (Persistent Buttons & Select) ───────
class DashboardView(View):
    """
    Persistent view attached to the dashboard embed.
    Controls: Project Restart Dropdown, Exec Command, Refresh, Kill PID.
    """

    def __init__(self, projects: list[ProjectStatus] | None = None):
        super().__init__(timeout=None)
        self.add_item(ProjectRestartSelect(projects))

    @button(
        label="Yenile",
        emoji="🔄",
        style=discord.ButtonStyle.primary,
        custom_id="dustops:refresh",
        row=1,
    )
    async def btn_refresh(self, interaction: discord.Interaction, btn: Button):
        if not _owner_only(interaction):
            await interaction.response.send_message("⛔ Yetkisiz işlem.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        from bot.dashboard import build_dashboard_embed

        async with httpx.AsyncClient(
            timeout=15,
            auth=(getattr(config, "WEB_USERNAME", ""), getattr(config, "WEB_PASSWORD", ""))
        ) as http:
            try:
                m_resp = await http.get(f"{API}/metrics")
                p_resp = await http.get(f"{API}/projects")

                metrics = SystemMetrics(**m_resp.json())
                projects = [ProjectStatus(**p) for p in p_resp.json()]
                embed = build_dashboard_embed(metrics, projects)

                new_view = DashboardView(projects)
                await interaction.message.edit(embed=embed, view=new_view)
                await interaction.followup.send("✅ Panel güncellendi.", ephemeral=True)
            except Exception as exc:
                await interaction.followup.send(f"❌ Güncelleme hatası: {exc}", ephemeral=True)

    @button(
        label="Komut Çalıştır",
        emoji="⚡",
        style=discord.ButtonStyle.success,
        custom_id="dustops:exec_cmd",
        row=1,
    )
    async def btn_exec(self, interaction: discord.Interaction, btn: Button):
        if not _owner_only(interaction):
            await interaction.response.send_message("⛔ Yetkisiz işlem.", ephemeral=True)
            return
        await interaction.response.send_modal(ExecCommandModal())

    @button(
        label="Süreç Sonlandır (Kill)",
        emoji="🛑",
        style=discord.ButtonStyle.danger,
        custom_id="dustops:kill",
        row=1,
    )
    async def btn_kill(self, interaction: discord.Interaction, btn: Button):
        if not _owner_only(interaction):
            await interaction.response.send_message("⛔ Yetkisiz işlem.", ephemeral=True)
            return
        await interaction.response.send_modal(KillModal())
