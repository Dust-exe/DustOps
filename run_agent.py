#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║          DustOps — Run Core Agent                        ║
║         uvicorn entrypoint for the local API             ║
╚══════════════════════════════════════════════════════════╝
"""

import sys
import os
import logging

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402 — triggers .env load
import uvicorn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-22s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║       ◈ DustOps Core Agent — Starting ◈         ║")
    print(f"║  Binding: {config.API_HOST}:{config.API_PORT}".ljust(51) + "║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    uvicorn.run(
        "agent.server:app",
        host=config.API_HOST,
        port=config.API_PORT,
        log_level="info",
        reload=False,
    )
