"""Security middleware for the Ollash Web UI."""
import os
import threading
import time
from collections import defaultdict
from functools import wraps

from flask import jsonify, request

# --------------- Rate Limiter ---------------


class RateLimiter:
    """Simple in-memory sliding-window rate limiter (per IP)."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        self._requests: dict = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            timestamps = self._requests[key]
            # Remove expired entries
            self._requests[key] = [t for t in timestamps if now - t < self.window]
            if len(self._requests[key]) >= self.max_requests:
                return False
            self._requests[key].append(now)
            return True


# Module-level rate limiters with different limits per concern
_api_limiter = RateLimiter(max_requests=60, window_seconds=60)
_chat_limiter = RateLimiter(max_requests=20, window_seconds=60)
_benchmark_limiter = RateLimiter(max_requests=5, window_seconds=60)


def rate_limit(limiter: RateLimiter = None):
    """Decorator that applies rate limiting to a Flask route."""
    if limiter is None:
        limiter = _api_limiter

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            client_ip = request.remote_addr or "unknown"
            if not limiter.is_allowed(client_ip):
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Rate limit exceeded. Please try again later.",
                        }
                    ),
                    429,
                )
            return f(*args, **kwargs)

        return wrapper

    return decorator


# Pre-built decorators for common use
rate_limit_api = rate_limit(_api_limiter)
rate_limit_chat = rate_limit(_chat_limiter)
rate_limit_benchmark = rate_limit(_benchmark_limiter)


# --------------- API Key Authentication ---------------


def require_api_key(f):
    """Decorator that enforces API key authentication if OLLASH_API_KEY is set.

    If the env var is not set, all requests are allowed (open mode).
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        expected_key = os.environ.get("OLLASH_API_KEY", "")
        if not expected_key:
            # No key configured — open access
            return f(*args, **kwargs)

        provided_key = request.headers.get("X-API-Key", "") or request.args.get(
            "api_key", ""
        )
        if provided_key != expected_key:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Invalid or missing API key.",
                    }
                ),
                401,
            )

        return f(*args, **kwargs)

    return wrapper


# --------------- CORS ---------------


def add_cors_headers(response):
    """After-request handler that adds CORS headers."""
    allowed_origins = os.environ.get("OLLASH_CORS_ORIGINS", "*")
    response.headers["Access-Control-Allow-Origin"] = allowed_origins
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
    return response
