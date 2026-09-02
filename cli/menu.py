"""
╔══════════════════════════════════════════════════════════╗
║        DustOps Terminal Control Center (Textual TUI)     ║
║  Cyberpunk Collapsible Project Dashboard, Keybindings    ║
║  Mouse Supported • Scoped Exec • Instant Restarts        ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
import httpx

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header,
    Footer,
    Static,
    Tree,
    Input,
    Button,
    Label,
    ProgressBar,
)
from textual.screen import ModalScreen
from textual.binding import Binding

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

API_URL = f"http://{config.API_HOST}:{config.API_PORT}"
AUTH = (getattr(config, "WEB_USERNAME", "admin"), getattr(config, "WEB_PASSWORD", ""))


# ─── API Helpers ─────────────────────────────────────────
def api_get(path: str, timeout: float = 4.0):
    try:
        r = httpx.get(f"{API_URL}{path}", auth=AUTH, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def api_post(path: str, json_data: dict | None = None, timeout: float = 35.0):
    try:
        r = httpx.post(f"{API_URL}{path}", json=json_data, auth=AUTH, timeout=timeout)
        return r.json() if r.status_code == 200 else {"error": f"HTTP {r.status_code}: {r.text}"}
    except Exception as e:
        return {"error": str(e)}


# ─── Command Execution Modal ─────────────────────────────
class CommandModal(ModalScreen[None]):
    """Modal to enter and execute a command in the selected project's directory."""

    CSS = """
    CommandModal {
        align: center middle;
    }
    #dialog {
        width: 80%;
        height: 80%;
        border: thick #b5179e;
        background: #0a0a0c;
        padding: 1 2;
    }
    #title {
        color: #4cc9f0;
        text-style: bold;
        margin-bottom: 1;
    }
    #cmd-input {
        border: solid #b5179e;
        margin-bottom: 1;
    }
    #output-scroll {
        height: 1fr;
        border: solid #333344;
        background: #050508;
        padding: 1;
        margin-bottom: 1;
    }
    #output-text {
        color: #e0e0e0;
    }
    .btn-row {
        align: right middle;
        height: auto;
    }
    """

    def __init__(self, project_id: str, project_name: str, project_cwd: str):
        super().__init__()
        self.project_id = project_id
        self.project_name = project_name
        self.project_cwd = project_cwd

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label(f"⚡ Shell Exec: {self.project_name} [dim]({self.project_cwd})[/dim]", id="title")
            yield Input(placeholder="Komut girin (örn: git status veya ls -la)...", id="cmd-input")
            with VerticalScroll(id="output-scroll"):
                yield Static("Hazır. Komutu yazıp Enter'a basın...", id="output-text")
            with Horizontal(classes="btn-row"):
                yield Button("Çalıştır", variant="primary", id="btn-run")
                yield Button("Kapat (ESC)", variant="default", id="btn-close")

    def on_mount(self) -> None:
        self.query_one("#cmd-input", Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        await self.execute_command(event.value)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-run":
            cmd = self.query_one("#cmd-input", Input).value
            await self.execute_command(cmd)
        elif event.button.id == "btn-close":
            self.dismiss()

    async def execute_command(self, cmd: str) -> None:
        if not cmd.strip():
            return

        out_static = self.query_one("#output-text", Static)
        out_static.update(f"⏳ Komut çalıştırılıyor: `{cmd}`...\nLütfen bekleyin...")

        res = api_post(f"/projects/{self.project_id}/exec", json_data={"command": cmd})
        if "error" in res and res.get("error"):
            out_static.update(f"[bold red]❌ HATA:[/bold red] {res.get('error')}")
            return

        stdout = res.get("stdout", "")
        stderr = res.get("stderr", "")
        exit_code = res.get("exit_code", 0)

        out_msg = f"[bold green]Çıkış Kodu: {exit_code}[/bold green]\n\n"
        if stdout:
            out_msg += f"[bold cyan]── STDOUT ──[/bold cyan]\n{stdout}\n"
        if stderr:
            out_msg += f"[bold yellow]── STDERR ──[/bold yellow]\n{stderr}\n"
        if not stdout and not stderr:
            out_msg += "[italic]Komut başarıyla tamamlandı (çıktı üretmedi).[/italic]"

        out_static.update(out_msg)


# ─── Log Viewer Modal ────────────────────────────────────
class LogModal(ModalScreen[None]):
    """Modal to display service details and quick logs."""

    CSS = """
    LogModal {
        align: center middle;
    }
    #log-dialog {
        width: 80%;
        height: 80%;
        border: thick #4cc9f0;
        background: #0a0a0c;
        padding: 1 2;
    }
    #log-title {
        color: #b5179e;
        text-style: bold;
        margin-bottom: 1;
    }
    #log-scroll {
        height: 1fr;
        border: solid #333344;
        background: #050508;
        padding: 1;
        margin-bottom: 1;
    }
    """

    def __init__(self, title: str, content: str):
        super().__init__()
        self.modal_title = title
        self.modal_content = content

    def compose(self) -> ComposeResult:
        with Vertical(id="log-dialog"):
            yield Label(self.modal_title, id="log-title")
            with VerticalScroll(id="log-scroll"):
                yield Static(self.modal_content)
            yield Button("Kapat", variant="primary", id="btn-close-log")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close-log":
            self.dismiss()


# ─── Main DustOps TUI Application ────────────────────────
class DustOpsTUI(App):
    """Modern Cyberpunk Collapsible Terminal UI for DustOps."""

    TITLE = "DustOps Control Center"
    SUB_TITLE = "Scoped Infrastructure & Microservices"

    CSS = """
    Screen {
        background: #0a0a0c;
        color: #e0e0e0;
    }
    Header {
        background: #14141e;
        color: #b5179e;
        text-style: bold;
    }
    Footer {
        background: #14141e;
        color: #4cc9f0;
    }
    #metrics-panel {
        height: 4;
        background: #101018;
        border-bottom: heavy #b5179e;
        padding: 0 1;
    }
    .metric-card {
        width: 1fr;
        align: center middle;
        padding: 0 1;
    }
    #main-container {
        padding: 1;
        height: 1fr;
    }
    Tree {
        background: #0a0a0c;
        color: #e0e0e0;
        border: solid #222233;
        padding: 1;
    }
    Tree:focus {
        border: double #4cc9f0;
    }
    .status-online {
        color: #4cc9f0;
        text-style: bold;
    }
    .status-error {
        color: #f72585;
        text-style: bold;
    }
    #status-bar {
        height: 1;
        background: #181824;
        color: #888899;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("r", "restart_item", "Yeniden Başlat (Restart)", show=True),
        Binding("c", "exec_command", "Komut Çalıştır (Exec)", show=True),
        Binding("l", "show_logs", "Detay / Loglar", show=True),
        Binding("u", "refresh_data", "Yenile", show=True),
        Binding("q", "quit", "Çıkış", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.projects_data: list[dict] = []
        self.selected_project: dict | None = None
        self.selected_service: dict | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="metrics-panel"):
            with Vertical(classes="metric-card"):
                yield Label("CPU: --%", id="lbl-cpu")
                yield ProgressBar(total=100, show_eta=False, id="pb-cpu")
            with Vertical(classes="metric-card"):
                yield Label("RAM: --%", id="lbl-ram")
                yield ProgressBar(total=100, show_eta=False, id="pb-ram")
            with Vertical(classes="metric-card"):
                yield Label("Disk: --%", id="lbl-disk")
                yield ProgressBar(total=100, show_eta=False, id="pb-disk")

        with Container(id="main-container"):
            tree: Tree[dict] = Tree("🌐 [bold #b5179e]Proje & Servis Ağacı[/bold #b5179e]")
            tree.root.expand()
            yield tree

        yield Static("Durum: Yükleniyor...", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.action_refresh_data()
        self.set_interval(5.0, self.action_refresh_data)

    def action_refresh_data(self) -> None:
        """Fetch metrics and projects from the Core Agent."""
        # 1. Update Metrics
        m_data = api_get("/metrics")
        if m_data:
            cpu_p = m_data.get("cpu_percent", 0.0)
            ram_p = m_data.get("ram_percent", 0.0)
            disk_p = m_data.get("disk_percent", 0.0)
            ram_mb = m_data.get("ram_used_mb", 0)
            ram_tot = m_data.get("ram_total_mb", 0)

            self.query_one("#lbl-cpu", Label).update(f"CPU: [bold cyan]{cpu_p:.1f}%[/bold cyan]")
            self.query_one("#pb-cpu", ProgressBar).progress = cpu_p

            self.query_one("#lbl-ram", Label).update(
                f"RAM: [bold magenta]{ram_p:.1f}%[/bold magenta] ({ram_mb:.0f}/{ram_tot:.0f} MB)"
            )
            self.query_one("#pb-ram", ProgressBar).progress = ram_p

            self.query_one("#lbl-disk", Label).update(f"Disk: [bold yellow]{disk_p:.1f}%[/bold yellow]")
            self.query_one("#pb-disk", ProgressBar).progress = disk_p

        # 2. Update Projects Tree
        p_data = api_get("/projects")
        if p_data:
            self.projects_data = p_data
            self._rebuild_tree(p_data)
            self.query_one("#status-bar", Static).update("Durum: [bold #4cc9f0]Çevrimiçi (Online)[/bold #4cc9f0] • Ağaç hazır")
        else:
            self.query_one("#status-bar", Static).update("[bold red]Agent API Bağlantısı Yok![/bold red]")

    def _rebuild_tree(self, projects: list[dict]) -> None:
        tree = self.query_one(Tree)
        # Preserve expanded state if possible
        expanded_ids = {node.data.get("id") for node in tree.root.children if node.data and node.is_expanded}

        tree.clear()
        tree.root.label = "📁 [bold #b5179e]DUSTOPS VDS ALTYAPISI[/bold #b5179e]"

        for proj in projects:
            p_id = proj.get("id")
            p_name = proj.get("name")
            is_healthy = proj.get("is_healthy", False)
            h_icon = "🟢" if is_healthy else "🔴"
            cwd = proj.get("cwd", "")

            p_node = tree.root.add(
                f"{h_icon} [bold #4cc9f0]{p_name}[/bold #4cc9f0] [dim]({cwd})[/dim]",
                data={"type": "project", "id": p_id, "name": p_name, "cwd": cwd, "raw": proj}
            )

            for s in proj.get("services", []):
                s_name = s.get("name")
                status = s.get("status")
                s_icon = "🟢" if status == "running" else "🔴"
                proc = s.get("process")
                port = s.get("port")
                port_str = f":{port}" if port else "—"

                if proc:
                    pid = proc.get("pid")
                    ram = proc.get("ram_mb", 0)
                    cpu = proc.get("cpu_percent", 0)
                    desc = f"PID: [yellow]{pid}[/yellow] | Port: [cyan]{port_str}[/cyan] | RAM: [green]{ram:.1f}MB[/green] | CPU: {cpu:.1f}%"
                else:
                    desc = f"[red]DURDURULDU[/red] | Port: [dim]{port_str}[/dim]"

                p_node.add_leaf(
                    f"  └─ {s_icon} [white]{s_name}[/white] • {desc}",
                    data={"type": "service", "project_id": p_id, "name": s_name, "raw": s, "parent_proj": proj}
                )

            if p_id in expanded_ids or not expanded_ids:
                p_node.expand()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        data = event.node.data
        if not data:
            return

        if data.get("type") == "project":
            self.selected_project = data
            self.selected_service = None
            self.query_one("#status-bar", Static).update(
                f"Seçili: [bold cyan]Proje {data.get('name')}[/bold cyan] [dim](Tuşlar: r=Restart, c=Exec, l=Detay)[/dim]"
            )
        elif data.get("type") == "service":
            self.selected_service = data
            self.selected_project = data.get("parent_proj")
            self.query_one("#status-bar", Static).update(
                f"Seçili: [bold yellow]Servis {data.get('name')}[/bold yellow] [dim](Tuşlar: r=Restart, l=Detay)[/dim]"
            )

    def action_restart_item(self) -> None:
        """Restart selected project or service."""
        node = self.query_one(Tree).cursor_node
        data = node.data if node else None
        if not data:
            self.notify("Önce yeniden başlatılacak bir proje veya servis seçin.", severity="warning")
            return

        proj_id = data.get("id") or data.get("project_id")
        proj_name = data.get("name", proj_id)

        self.notify(f"🚀 {proj_name} yeniden başlatılıyor...", severity="information")
        res = api_post(f"/projects/{proj_id}/restart")

        if res.get("success"):
            self.notify(f"✅ {proj_name} yeniden başlatıldı!", severity="information")
        else:
            self.notify(f"❌ Yeniden başlatma hatası: {res.get('detail', res.get('error'))}", severity="error")

        self.action_refresh_data()

    def action_exec_command(self) -> None:
        """Open command execution popup for selected project."""
        node = self.query_one(Tree).cursor_node
        data = node.data if node else None
        if not data:
            self.notify("Önce bir proje seçin.", severity="warning")
            return

        if data.get("type") == "service":
            proj_data = data.get("parent_proj", {})
            proj_id = proj_data.get("id")
            proj_name = proj_data.get("name", proj_id)
            proj_cwd = proj_data.get("cwd", "")
        else:
            proj_id = data.get("id")
            proj_name = data.get("name", proj_id)
            proj_cwd = data.get("cwd", "")

        if not proj_id:
            self.notify("Geçerli bir proje seçilmedi.", severity="warning")
            return

        self.push_screen(CommandModal(project_id=proj_id, project_name=proj_name, project_cwd=proj_cwd))

    def action_show_logs(self) -> None:
        """Show details and process/service snapshot."""
        node = self.query_one(Tree).cursor_node
        data = node.data if node else None
        if not data:
            self.notify("Önce bir öğe seçin.", severity="warning")
            return

        if data.get("type") == "service":
            s_raw = data.get("raw", {})
            proc = s_raw.get("process") or {}
            content = (
                f"[bold cyan]Servis Adı:[/bold cyan] {s_raw.get('name')}\n"
                f"[bold cyan]Durum:[/bold cyan] {s_raw.get('status')}\n"
                f"[bold cyan]Port:[/bold cyan] {s_raw.get('port') or 'Yok'}\n"
                f"[bold cyan]Restart Komutu:[/bold cyan] {s_raw.get('restart_cmd')}\n\n"
                f"[bold green]── Canlı Süreç Bilgisi ──[/bold green]\n"
                f"PID: {proc.get('pid', '—')}\n"
                f"Süreç İsmi: {proc.get('name', '—')}\n"
                f"Komut Satırı: {proc.get('cmdline', '—')}\n"
                f"CPU Kullanımı: {proc.get('cpu_percent', 0)}%\n"
                f"RAM Kullanımı: {proc.get('ram_mb', 0)} MB\n"
            )
            title = f"🔍 Servis Detayları: {data.get('name')}"
        else:
            p_raw = data.get("raw", {})
            services = p_raw.get("services", [])
            s_list = "\n".join([f"• {s.get('name')}: {s.get('status')}" for s in services])
            content = (
                f"[bold cyan]Proje ID:[/bold cyan] {p_raw.get('id')}\n"
                f"[bold cyan]Proje Adı:[/bold cyan] {p_raw.get('name')}\n"
                f"[bold cyan]Çalışma Dizini (CWD):[/bold cyan] {p_raw.get('cwd')}\n"
                f"[bold cyan]Genel Sağlık:[/bold cyan] {'🟢 Sağlıklı' if p_raw.get('is_healthy') else '🔴 Hata/Eksik'}\n\n"
                f"[bold green]── Bağlı Servisler ──[/bold green]\n{s_list}\n"
            )
            title = f"📁 Proje Detayları: {data.get('name')}"

        self.push_screen(LogModal(title=title, content=content))


def main():
    app = DustOpsTUI()
    app.run()


if __name__ == "__main__":
    main()
