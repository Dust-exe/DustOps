import os
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = "/root/DustOps/docs/assets"
os.makedirs(ASSETS_DIR, exist_ok=True)

FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FONT_SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# ═════════════════════════════════════════════════════════
# 1. PIXEL-PERFECT TERMINAL TUI MOCKUP
# ═════════════════════════════════════════════════════════
def render_tui():
    width, height = 980, 600
    img = Image.new("RGBA", (width, height), (10, 10, 14, 255))
    draw = ImageDraw.Draw(img)

    # Window Header
    draw.rectangle([0, 0, width, 40], fill=(20, 20, 28, 255))
    draw.line([0, 40, width, 40], fill=(45, 45, 60, 255), width=1)

    # Window dots
    draw.ellipse([18, 14, 30, 26], fill=(255, 95, 86, 255))
    draw.ellipse([38, 14, 50, 26], fill=(255, 189, 46, 255))
    draw.ellipse([58, 14, 70, 26], fill=(39, 201, 63, 255))

    font_title = ImageFont.truetype(FONT_SANS_BOLD, 12)
    draw.text((width//2 - 140, 13), "root@vds: ~ · dustops (Textual Control Center)", font=font_title, fill=(170, 170, 190, 255))

    # Metrics Bar
    draw.rectangle([20, 56, width-20, 116], fill=(16, 16, 24, 255), outline=(181, 23, 158, 180), width=1)
    font_bold = ImageFont.truetype(FONT_MONO_BOLD, 12)
    font_reg = ImageFont.truetype(FONT_MONO, 12)

    # CPU Gauge
    draw.text((36, 68), "CPU: 12.4%", font=font_bold, fill=(76, 201, 240, 255))
    draw.text((36, 88), "[███░░░░░░░░░░░░░░░░░░]", font=font_reg, fill=(76, 201, 240, 200))

    # RAM Gauge
    draw.text((350, 68), "RAM: 68.2% (2671/3916 MB)", font=font_bold, fill=(232, 121, 249, 255))
    draw.text((350, 88), "[██████████████░░░░░░░]", font=font_reg, fill=(232, 121, 249, 200))

    # Disk Gauge
    draw.text((690, 68), "Disk: 25.5% (9.8/38.5 GB)", font=font_bold, fill=(253, 245, 0, 255))
    draw.text((690, 88), "[█████░░░░░░░░░░░░░░░░]", font=font_reg, fill=(253, 245, 0, 200))

    # Tree Box
    draw.rectangle([20, 130, width-20, height-55], fill=(12, 12, 18, 255), outline=(50, 50, 70, 255), width=1)
    
    draw.text((36, 146), "DUSTOPS VDS ALTYAPISI (PROJECT CLUSTERS)", font=font_bold, fill=(181, 23, 158))

    rows = [
        # (indent, is_header, name, path_or_specs)
        (36, True, "dust-studio.com", "(/root/dust-studio)"),
        (64, False, "Main Bot", "PID: 1506   | Port: —     | RAM: 49.3 MB | CPU: 0.0%"),
        (36, True, "Dust Studio Kayit", "(/root/dust studio kayıt)"),
        (64, False, "Kayit Bot", "PID: 1512   | Port: —     | RAM: 48.0 MB | CPU: 0.0%"),
        (36, True, "Dust Analyz (API)", "(/root/dust)"),
        (64, False, "API (Gunicorn)", "PID: 736216 | Port: :8081 | RAM: 64.6 MB | CPU: 0.2%"),
        (36, True, "Arac Galeri", "(/var/www/potex-galeri)"),
        (64, False, "Frontend (Next.js)", "PID: 1601   | Port: :3000 | RAM: 97.8 MB | CPU: 0.0%"),
        (36, True, "DustOps Suite", "(/root/DustOps)"),
        (64, False, "Core Agent Daemon", "PID: 836104 | Port: :4141 | RAM: 45.7 MB | CPU: 0.0%"),
        (64, False, "Discord Bot Client", "PID: 836108 | Port: —     | RAM: 61.8 MB | CPU: 0.0%"),
    ]

    y = 175
    for indent, is_header, name, detail in rows:
        # draw green status dot
        draw.ellipse([indent, y+3, indent+8, y+11], fill=(16, 185, 129, 255))

        if is_header:
            draw.text((indent+16, y), name, font=font_bold, fill=(76, 201, 240))
            draw.text((indent+18 + int(len(name)*9.5), y), detail, font=font_reg, fill=(140, 140, 160))
            y += 24
        else:
            draw.text((indent+16, y), f"└─ {name.ljust(20)} | {detail}", font=font_reg, fill=(210, 210, 225))
            y += 22

    # Bottom Keybindings footer
    draw.rectangle([20, height-46, width-20, height-18], fill=(20, 20, 30, 255), outline=(40, 40, 55, 255), width=1)
    keys = "[r] Restart   [c] Exec Command   [l] Service Logs   [u] Sync Telemetry   [q] Quit"
    draw.text((36, height-38), keys, font=font_reg, fill=(76, 201, 240, 255))

    out_path = os.path.join(ASSETS_DIR, "terminal_tui.png")
    img.save(out_path, "PNG")
    print(f"Saved {out_path}")


# ═════════════════════════════════════════════════════════
# 2. PIXEL-PERFECT DISCORD BOT DM EMBED MOCKUP
# ═════════════════════════════════════════════════════════
def render_discord():
    width, height = 780, 690
    img = Image.new("RGBA", (width, height), (49, 51, 56, 255))
    draw = ImageDraw.Draw(img)

    font_sans = ImageFont.truetype(FONT_SANS, 14)
    font_bold = ImageFont.truetype(FONT_SANS_BOLD, 14)
    font_embed_title = ImageFont.truetype(FONT_SANS_BOLD, 16)
    font_code = ImageFont.truetype(FONT_MONO, 12)
    font_code_bold = ImageFont.truetype(FONT_MONO_BOLD, 12)

    # Bot Avatar (Paste icon or draw purple ring)
    draw.ellipse([24, 24, 66, 66], fill=(168, 85, 247, 255))
    draw.ellipse([34, 34, 56, 56], fill=(30, 30, 35, 255))
    draw.text((41, 37), "D", font=font_bold, fill=(255, 255, 255))

    # Bot Name & Tag
    draw.text((78, 26), "Dust Studio", font=font_bold, fill=(255, 255, 255, 255))
    
    # APP Badge
    draw.rectangle([166, 28, 202, 43], fill=(88, 101, 242, 255))
    font_app = ImageFont.truetype(FONT_SANS_BOLD, 10)
    draw.text((171, 30), "APP", font=font_app, fill=(255, 255, 255, 255))
    
    draw.text((212, 28), "Today at 11:58 PM", font=font_sans, fill=(148, 155, 164, 255))

    # Discord Embed Card
    embed_x, embed_y = 78, 56
    embed_w, embed_h = 670, 485
    draw.rectangle([embed_x, embed_y, embed_x + embed_w, embed_y + embed_h], fill=(43, 45, 49, 255))
    # Purple Left Border
    draw.rectangle([embed_x, embed_y, embed_x + 4, embed_y + embed_h], fill=(168, 85, 247, 255))

    # Embed Title
    draw.text((embed_x + 16, embed_y + 16), "DustOps — Infrastructure Control Panel", font=font_embed_title, fill=(255, 255, 255, 255))

    # System Resources Field
    draw.text((embed_x + 16, embed_y + 46), "System Resources", font=font_bold, fill=(180, 185, 195, 255))
    res_text = "CPU: 12.4% [███░░░░░░░]  |  RAM: 68.2% [████████░░] (2.6/3.9 GB)  |  Disk: 25.5%"
    draw.text((embed_x + 16, embed_y + 68), res_text, font=font_code, fill=(220, 225, 235, 255))

    # Project Groups
    y = embed_y + 102
    projects = [
        ("dust-studio.com  `dust-studio`", [("Main Bot", "PID: 1506 | :— | 49.3 MB | 0.0%")]),
        ("Dust Studio Kayit  `dust-studio-kayit`", [("Kayit Bot", "PID: 1512 | :— | 48.0 MB | 0.0%")]),
        ("Dust Analyz (API)  `dust-analyz`", [("API (Gunicorn)", "PID: 736216 | :8081 | 64.6 MB | 0.2%")]),
        ("Arac Galeri  `arac-galeri`", [("Frontend (Next.js)", "PID: 1601 | :3000 | 97.8 MB | 0.0%")]),
        ("DustOps Suite  `dustops`", [("Core Agent", "PID: 836104 | :4141 | 45.7 MB | 0.0%"),
                                     ("Discord Bot", "PID: 836108 | :— | 61.8 MB | 0.0%")]),
    ]

    for p_title, services in projects:
        draw.text((embed_x + 16, y), p_title, font=font_bold, fill=(255, 255, 255, 255))
        # Draw checkmark badge
        draw.text((embed_x + 16 + int(len(p_title)*9.2), y), "[OK]", font=font_code_bold, fill=(16, 185, 129))
        y += 20

        for idx, (s_name, s_spec) in enumerate(services):
            branch = "└─" if idx == len(services)-1 else "├─"
            draw.text((embed_x + 16, y), branch, font=font_code, fill=(140, 140, 150))
            # status dot
            draw.ellipse([embed_x + 36, y+3, embed_x + 44, y+11], fill=(16, 185, 129, 255))
            draw.text((embed_x + 50, y), f"{s_name} | {s_spec}", font=font_code, fill=(205, 210, 220, 255))
            y += 18
        y += 8

    # Embed Footer
    draw.text((embed_x + 16, embed_y + embed_h - 24), "DustOps • Scoped Infrastructure Management", font=font_sans, fill=(148, 155, 164, 255))

    # Dropdown Component
    comp_y = embed_y + embed_h + 12
    draw.rectangle([embed_x, comp_y, embed_x + embed_w, comp_y + 40], fill=(35, 36, 40, 255), outline=(60, 62, 68, 255), width=1)
    draw.text((embed_x + 16, comp_y + 11), "Yeniden Baslatilacak Projeyi Sec (Restart Project)...", font=font_sans, fill=(180, 185, 195, 255))
    draw.text((embed_x + embed_w - 24, comp_y + 11), "v", font=font_bold, fill=(180, 185, 195, 255))

    # Action Buttons Row
    btn_y = comp_y + 50
    # Refresh
    draw.rectangle([embed_x, btn_y, embed_x + 130, btn_y + 36], fill=(88, 101, 242, 255))
    draw.text((embed_x + 30, btn_y + 9), "Yenile", font=font_bold, fill=(255, 255, 255, 255))

    # Exec Command
    draw.rectangle([embed_x + 142, btn_y, embed_x + 320, btn_y + 36], fill=(36, 128, 70, 255))
    draw.text((embed_x + 158, btn_y + 9), "Komut Calistir", font=font_bold, fill=(255, 255, 255, 255))

    # Kill Process
    draw.rectangle([embed_x + 332, btn_y, embed_x + 520, btn_y + 36], fill=(218, 55, 60, 255))
    draw.text((embed_x + 348, btn_y + 9), "Surec Sonlandir", font=font_bold, fill=(255, 255, 255, 255))

    out_path = os.path.join(ASSETS_DIR, "discord_bot.png")
    img.save(out_path, "PNG")
    print(f"Saved {out_path}")

if __name__ == "__main__":
    render_tui()
    render_discord()
