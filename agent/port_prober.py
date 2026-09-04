"""
╔══════════════════════════════════════════════════════════╗
║          DustOps Agent — Port & SSL Prober Matrix        ║
║   Uptime, HTTP Status, Ping ms & SSL Expiry Countdown    ║
╚══════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import asyncio
import socket
import ssl
import time
import logging
from datetime import datetime, timezone
import httpx

logger = logging.getLogger("dustops.prober")

PROBE_TARGETS = [
    {
        "id": "dust-studio-site",
        "name": "🌐 dust-studio.com",
        "url": "https://dust-studio.com",
        "host": "dust-studio.com",
        "port": 443,
        "check_ssl": True,
    },
    {
        "id": "arac-galeri",
        "name": "🚗 Araç Galeri (Next.js)",
        "url": "http://127.0.0.1:3000",
        "host": "127.0.0.1",
        "port": 3000,
        "check_ssl": False,
    },
    {
        "id": "dust-studio-webhook",
        "name": "🔮 Discord Bot Webhook",
        "url": "http://127.0.0.1:3050/health",
        "host": "127.0.0.1",
        "port": 3050,
        "check_ssl": False,
    },
    {
        "id": "dustops-agent",
        "name": "🛡️ DustOps Core Agent",
        "url": "http://127.0.0.1:4141/health",
        "host": "127.0.0.1",
        "port": 4141,
        "check_ssl": False,
    },
    {
        "id": "dust-analyz",
        "name": "📊 Dust Analyz API",
        "url": "http://127.0.0.1:8081",
        "host": "127.0.0.1",
        "port": 8081,
        "check_ssl": False,
    },
]

_probe_cache = {
    "timestamp": 0.0,
    "data": []
}

def get_ssl_expiry(hostname: str, port: int = 443) -> dict:
    """Query TLS socket for certificate validity and days remaining."""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=3.5) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                not_after = cert.get("notAfter")
                if not_after:
                    # e.g., 'May 25 12:00:00 2026 GMT'
                    expiry_date = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                    now = datetime.now(timezone.utc)
                    days_left = max(0, (expiry_date - now).days)
                    return {
                        "valid": True,
                        "expiry_date": expiry_date.strftime("%Y-%m-%d"),
                        "days_left": days_left,
                        "issuer": dict(x[0] for x in cert.get("issuer", [])).get("commonName", "Unknown CA"),
                        "status": "warning" if days_left < 14 else "ok"
                    }
    except Exception as e:
        logger.debug("SSL check failed for %s: %s", hostname, e)
    return {
        "valid": False,
        "expiry_date": "N/A",
        "days_left": 0,
        "issuer": "N/A",
        "status": "error"
    }

async def probe_single(target: dict) -> dict:
    """Probe a single service endpoint."""
    t0 = time.time()
    status_code = None
    online = False
    error_msg = None

    try:
        async with httpx.AsyncClient(timeout=3.0, verify=False) as client:
            resp = await client.get(target["url"])
            status_code = resp.status_code
            online = resp.status_code < 500
    except httpx.ConnectError:
        error_msg = "Bağlantı Reddedildi"
    except httpx.TimeoutException:
        error_msg = "Zaman Aşımı"
    except Exception as e:
        error_msg = str(e)[:30]

    latency_ms = round((time.time() - t0) * 1000, 1)

    result = {
        "id": target["id"],
        "name": target["name"],
        "url": target["url"],
        "port": target["port"],
        "online": online,
        "status_code": status_code,
        "latency_ms": latency_ms if online else 0,
        "error": error_msg,
        "ssl": None
    }

    if target.get("check_ssl") and target.get("host"):
        result["ssl"] = get_ssl_expiry(target["host"], target["port"])

    return result

async def probe_all_services(force: bool = False) -> list[dict]:
    """Probe all targets concurrently with caching."""
    now = time.time()
    if not force and _probe_cache["data"] and (now - _probe_cache["timestamp"] < 25.0):
        return _probe_cache["data"]

    tasks = [probe_single(t) for t in PROBE_TARGETS]
    results = await asyncio.gather(*tasks)

    _probe_cache["timestamp"] = now
    _probe_cache["data"] = list(results)
    return _probe_cache["data"]
