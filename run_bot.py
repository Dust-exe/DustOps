#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║          DustOps — Run Discord Bot                       ║
╚══════════════════════════════════════════════════════════╝
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402
from bot.client import DustOpsBot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-22s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)

if __name__ == "__main__":
    if not config.DISCORD_TOKEN or config.DISCORD_TOKEN == "YOUR_DISCORD_BOT_TOKEN":
        print()
        print("╔══════════════════════════════════════════════════╗")
        print("║  ✗ HATA: DISCORD_TOKEN ayarlanmamış!            ║")
        print("║  .env dosyasını kontrol edin.                   ║")
        print("╚══════════════════════════════════════════════════╝")
        print()
        sys.exit(1)

    if not config.OWNER_USER_ID:
        print()
        print("╔══════════════════════════════════════════════════╗")
        print("║  ✗ HATA: OWNER_USER_ID ayarlanmamış!            ║")
        print("║  .env dosyasını kontrol edin.                   ║")
        print("╚══════════════════════════════════════════════════╝")
        print()
        sys.exit(1)

    bot = DustOpsBot()
    bot.run(config.DISCORD_TOKEN, log_handler=None)
