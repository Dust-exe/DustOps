#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║          DustOps — Run Desktop GUI                       ║
╚══════════════════════════════════════════════════════════╝
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402 — triggers .env load

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-22s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)

if __name__ == "__main__":
    from gui.app import DustOpsApp

    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║    ◈ DustOps Desktop GUI — Launching ◈          ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    app = DustOpsApp()
    app.mainloop()
