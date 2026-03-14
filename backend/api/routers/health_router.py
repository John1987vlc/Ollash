"""Health check router — real Ollama connectivity check."""

import time
import psutil
import requests
from fastapi import APIRouter

from backend.core.config import config as app_config

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/")
async def get_system_health():
    """System health: CPU/RAM stats and Ollama connectivity."""
    ollama_url = getattr(app_config, "OLLAMA_URL", "http://localhost:11434")
    models_available: list[str] = []
    ollama_connected = False
    ollama_latency_ms: float | None = None

    try:
        t0 = time.monotonic()
        resp = requests.get(f"{ollama_url}/api/tags", timeout=3)
        ollama_latency_ms = round((time.monotonic() - t0) * 1000, 1)
        if resp.status_code == 200:
            ollama_connected = True
            models_available = [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass

    try:
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
    except Exception:
        cpu = 0.0
        ram = 0.0

    return {
        "status": "ok" if ollama_connected else "degraded",
        "ollama_connected": ollama_connected,
        "ollama_url": ollama_url,
        "ollama_latency_ms": ollama_latency_ms,
        "models_available": models_available,
        "cpu_percent": cpu,
        "ram_percent": ram,
    }
