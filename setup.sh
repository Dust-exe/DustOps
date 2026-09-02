#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════╗
# ║        DustOps — VDS Kurulum Scripti (setup.sh)          ║
# ║  Tek komutla bağımlılıkları kur + dustops global komut   ║
# ╚══════════════════════════════════════════════════════════╝
set -e

DUSTOPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON=$(command -v python3 || command -v python)

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║       ◈ DustOps Setup — Başlıyor ◈             ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── 1. Python kontrolü ───────────────────────────────────
if [ -z "$PYTHON" ]; then
    echo "✗ Python3 bulunamadı. Kurun: apt install python3"
    exit 1
fi
echo "✓ Python: $($PYTHON --version)"

# ── 2. pip bağımlılıklarını kur ──────────────────────────
echo ""
echo "► Bağımlılıklar kuruluyor…"
$PYTHON -m pip install --break-system-packages \
    fastapi uvicorn psutil python-dotenv pydantic httpx \
    "discord.py>=2.4.0" rich textual 2>&1 | grep -E "(Successfully|already|ERROR)" || true
echo "✓ Bağımlılıklar hazır."

# ── 3. CLI scriptini çalıştırılabilir yap ────────────────
chmod +x "$DUSTOPS_DIR/cli/menu.py"

# ── 4. dustops global komutunu oluştur ───────────────────
WRAPPER="/usr/local/bin/dustops"

cat > "$WRAPPER" << EOF
#!/usr/bin/env bash
# DustOps CLI Wrapper — Otomatik oluşturuldu
DUSTOPS_DIR="$DUSTOPS_DIR"
cd "\$DUSTOPS_DIR"
exec $PYTHON "\$DUSTOPS_DIR/cli/menu.py" "\$@"
EOF

chmod +x "$WRAPPER"
echo "✓ Global komut kuruldu: dustops"

# ── 5. .env kontrolü ─────────────────────────────────────
if [ ! -f "$DUSTOPS_DIR/.env" ]; then
    cp "$DUSTOPS_DIR/.env.example" "$DUSTOPS_DIR/.env"
    echo "⚠ .env dosyası oluşturuldu — DISCORD_TOKEN ve OWNER_USER_ID ayarlayın!"
else
    echo "✓ .env dosyası mevcut."
fi

# ── 6. PM2 ile otomatik başlatma (opsiyonel) ─────────────
if command -v pm2 &> /dev/null; then
    echo ""
    echo "► PM2 bulundu — servisleri kayıt edelim mi?"
    read -p "  Agent ve Bot'u PM2'ye ekle? (y/N): " pm2_confirm
    if [[ "$pm2_confirm" =~ ^[Yy]$ ]]; then
        pm2 start "$DUSTOPS_DIR/run_agent.py" \
            --name "dustops-agent" \
            --interpreter "$PYTHON" \
            --cwd "$DUSTOPS_DIR" 2>/dev/null || echo "  (dustops-agent zaten PM2'de)"

        pm2 start "$DUSTOPS_DIR/run_bot.py" \
            --name "dustops-bot" \
            --interpreter "$PYTHON" \
            --cwd "$DUSTOPS_DIR" 2>/dev/null || echo "  (dustops-bot zaten PM2'de)"

        pm2 save
        echo "✓ PM2 servisleri kaydedildi."
    fi
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║           ◈ Kurulum Tamamlandı! ◈              ║"
echo "╠══════════════════════════════════════════════════╣"
echo "║  Kullanım:                                       ║"
echo "║  $ dustops            → Menüyü aç               ║"
echo "║  $ dustops metrics    → Anlık metrikler         ║"
echo "║  $ dustops ps         → Süreç listesi           ║"
echo "║  $ dustops live       → Canlı izleme            ║"
echo "║  $ python3 run_agent.py  → Core Agent başlat   ║"
echo "║  $ python3 run_bot.py    → Discord Bot başlat  ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
