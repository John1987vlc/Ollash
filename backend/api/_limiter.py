"""Shared slowapi Limiter instance.

Import this wherever per-route @limiter.limit() decorators are needed.
The same instance is wired into app.state.limiter by create_app() so the
SlowAPIMiddleware enforces the default_limits globally.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])
