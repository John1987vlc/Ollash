"""
FastAPI dependency providers.

Replace Flask's `current_app.config.get("key")` pattern with typed
FastAPI dependencies using `request.app.state`.
"""

import logging
from functools import wraps

from fastapi import HTTPException, Request

from backend.utils.core.system.event_publisher import EventPublisher
from backend.utils.core.system.agent_logger import AgentLogger

logger = logging.getLogger(__name__)


def service_error_handler(fn):
    """Decorator: converts unhandled exceptions in route handlers to HTTP 500.

    Re-raises HTTPException as-is so intentional 4xx/5xx codes pass through.
    All other exceptions are logged and converted to a generic 500.
    """
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
