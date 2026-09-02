@echo off
:: ╔══════════════════════════════════════════════════════╗
:: ║   DustOps — Windows SSH Tunnel + GUI Başlatıcı       ║
:: ║   Çift tıkla çalıştır, her şey otomatik olur         ║
:: ╚══════════════════════════════════════════════════════╝
title DustOps — VDS Tunnel

:: ── Ayarlar ─────────────────────────────────────────────
:: VDS IP adresini buraya yaz:
set VDS_IP=YOUR_VDS_IP_HERE
set VDS_USER=root
set LOCAL_PORT=4141
set REMOTE_PORT=4141

:: GUI Python scripti (kendi yolunu ayarla):
set GUI_SCRIPT=%~dp0run_gui.py

:: ────────────────────────────────────────────────────────
echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║      ◈ DustOps VDS Tunnel Başlatılıyor ◈       ║
echo  ╚══════════════════════════════════════════════════╝
echo.
echo  VDS   : %VDS_USER%@%VDS_IP%
echo  Tünel : 127.0.0.1:%LOCAL_PORT% → VDS:%REMOTE_PORT%
echo.
echo  [*] SSH tüneli arka planda açılıyor...

:: SSH tünelini arka planda başlat
start "DustOps SSH Tunnel" /min ssh -N -L %LOCAL_PORT%:127.0.0.1:%REMOTE_PORT% %VDS_USER%@%VDS_IP%

:: Tünelin kurulması için kısa bekle
echo  [*] Tünel kurulumu bekleniyor (3 saniye)...
timeout /t 3 /nobreak > nul

:: Bağlantıyı test et
echo  [*] Agent'a ping atılıyor...
curl -s -o nul -w "%%{http_code}" http://127.0.0.1:%LOCAL_PORT%/health > %TEMP%\dustops_ping.txt 2>nul
set /p PING_STATUS=<%TEMP%\dustops_ping.txt

if "%PING_STATUS%"=="200" (
    echo  [+] Agent ONLINE! Bağlantı başarılı.
    echo.
) else (
    echo  [!] Agent yanıt vermedi. VDS'de agent çalışıyor mu?
    echo  [!] VDS'de: python3 /root/DustOps/run_agent.py
    echo.
    echo  [?] Yine de GUI'yi açmaya devam edilsin mi?
    pause
)

:: GUI'yi başlat
echo  [*] DustOps GUI başlatılıyor...
python run_gui.py

:: GUI kapanınca SSH tünelini de kapat
echo.
echo  [*] GUI kapandı, SSH tüneli durduruluyor...
taskkill /f /im ssh.exe > nul 2>&1
echo  [*] Tünel kapatıldı.
timeout /t 2 /nobreak > nul
