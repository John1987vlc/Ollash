"""
FastAPI dependency providers.

Replace Flask's `current_app.config.get("key")` pattern with typed
FastAPI dependencies using `request.app.state`.
"""

import logging
import os
from functools import wraps
from pathlib import Path

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.utils.core.system.event_publisher import EventPublisher
from backend.utils.core.system.agent_logger import AgentLogger

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)
_AUTH_DB = Path(os.environ.get("OLLASH_ROOT_DIR", ".ollash")) / "auth.db"


def get_current_user_dep(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_api_key: str | None = None,
) -> dict:
    """FastAPI dependency: validate JWT or API key, return user dict or raise 401."""
    from backend.utils.auth import decode_token, hash_api_key

    if credentials and credentials.credentials:
        try:
            payload = decode_token(credentials.credentials)
            return {"user_id": int(payload["sub"]), "username": payload["username"]}
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    if x_api_key:
        from backend.utils.core.system.db.user_store import UserStore

        user = UserStore(_AUTH_DB).verify_api_key(hash_api_key(x_api_key))
        if user:
            return {"user_id": user["user_id"], "username": user["username"]}
        raise HTTPException(status_code=401, detail="Invalid API key")

    raise HTTPException(status_code=401, detail="Not authenticated")


def get_optional_user_dep(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_api_key: str | None = None,
) -> dict | None:
    """Like get_current_user_dep but returns None for unauthenticated requests."""
    try:
        return get_current_user_dep(credentials, x_api_key)
    except HTTPException:
        return None


# ---------------------------------------------------------------------------
# Service dependencies
# ---------------------------------------------------------------------------


def service_error_handler(fn):
    """Decorator: convert unhandled exceptions to HTTP 500 (pass through HTTPException)."""

    @wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Unhandled error in %s: %s", fn.__name__, exc)
            raise HTTPException(status_code=500, detail=str(exc))

    return wrapper


def get_event_publisher(request: Request) -> EventPublisher:
    return request.app.state.event_publisher


def get_alert_manager(request: Request):
    return request.app.state.alert_manager


def get_automation_manager(request: Request):
    return request.app.state.automation_manager


def get_notification_manager(request: Request):
    return request.app.state.notification_manager


def get_chat_event_bridge(request: Request):
    return request.app.state.chat_event_bridge


def get_logger(request: Request) -> AgentLogger:
    return request.app.state.logger


def get_ollash_root_dir(request: Request):
    return request.app.state.ollash_root_dir
