"""Privacy audit router — exposes network call log and local-mode status.

Endpoints
---------
GET /api/privacy/status  — is_local flag + allowed hosts list (no auth required)
GET /api/privacy/audit   — full session call log + summary (auth required)
POST /api/privacy/clear  — clear the call log (auth required)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.deps import get_current_user_dep
from backend.core.config import get_config

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


def _get_ollama_url() -> str:
    """Read the configured Ollama URL via the unified config system."""
    return get_config().OLLAMA_URL


def _is_local_url(url: str) -> bool:
    from urllib.parse import urlparse

    host = urlparse(url).hostname or ""
    return host.lower() in {"localhost", "127.0.0.1", "::1"}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status")
def privacy_status() -> dict:
    """Return local-mode detection result.  No auth required (used by UI badge)."""
    from backend.utils.core.system.network_monitor import network_monitor

    ollama_url = _get_ollama_url()
    is_local = _is_local_url(ollama_url)
    return {
        "is_local": is_local,
        "ollama_url": ollama_url,
        "allowed_hosts": network_monitor.get_allowed_hosts(),
        "mode": "local" if is_local else "remote",
    }


@router.get("/audit")
def privacy_audit(
    limit: int = 100,
    user: dict = Depends(get_current_user_dep),
) -> dict:
    """Return session-level network call log + summary."""
    from backend.utils.core.system.network_monitor import network_monitor

    return {
        "summary": network_monitor.summary(),
        "log": network_monitor.get_log(limit=limit),
    }


@router.post("/clear", status_code=204)
def clear_audit_log(user: dict = Depends(get_current_user_dep)) -> None:
    """Clear the in-memory network call log."""
    from backend.utils.core.system.network_monitor import network_monitor

    network_monitor.clear()
