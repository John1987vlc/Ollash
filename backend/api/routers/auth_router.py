"""Auth router — local JWT auth, user accounts and API keys.

Endpoints
---------
POST   /api/auth/register             Create a new local user account
POST   /api/auth/login                Authenticate and receive a JWT Bearer token
GET    /api/auth/me                   Return current user profile (requires auth)
POST   /api/auth/api-keys             Generate a new API key (requires auth)
GET    /api/auth/api-keys             List all API keys for the user (requires auth)
DELETE /api/auth/api-keys/{key_id}    Revoke an API key (requires auth)
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.api._limiter import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])

_DB_PATH = Path(os.environ.get("OLLASH_ROOT_DIR", ".ollash")) / "auth.db"
_MAX_API_KEYS = 20  # per user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store():
    from backend.utils.core.system.db.user_store import UserStore

    return UserStore(_DB_PATH)


# Lazy import to avoid circular dependency at module load time
def _get_current_user():
    from backend.api.deps import get_current_user_dep

    return get_current_user_dep


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class ApiKeyRequest(BaseModel):
    name: str = "default"


# ---------------------------------------------------------------------------
# Public endpoints (no auth required)
# ---------------------------------------------------------------------------


@router.get("/")
async def auth_index():
    return {"status": "ok", "endpoints": ["/register", "/login", "/me", "/api-keys"]}


@router.post("/register", status_code=201)
async def register(req: RegisterRequest):
    """Create a new local user account (username ≥3 chars, password ≥6 chars)."""
    username = req.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="username must be at least 3 characters")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="password must be at least 6 characters")

    store = _store()
    if store.get_user_by_username(username):
        raise HTTPException(status_code=409, detail="Username already taken")

    from backend.utils.auth import hash_password

    user_id = store.create_user(username, hash_password(req.password))
    return {"status": "created", "user_id": user_id, "username": username}


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, req: LoginRequest):
    """Authenticate and return a JWT Bearer token (valid 24 h by default)."""
    store = _store()
    user = store.get_user_by_username(req.username.strip())
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    from backend.utils.auth import create_access_token, verify_password

    if not verify_password(req.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user_id=user["id"], username=user["username"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user["username"],
        "user_id": user["id"],
    }


# ---------------------------------------------------------------------------
# Protected endpoints (JWT or API key required)
# ---------------------------------------------------------------------------


@router.get("/me")
async def get_me(current_user: dict = Depends(_get_current_user())):
    """Return the current authenticated user's profile."""
    return {
        "user_id": current_user["user_id"],
        "username": current_user["username"],
    }


@router.post("/api-keys", status_code=201)
async def create_api_key(
    req: ApiKeyRequest,
    current_user: dict = Depends(_get_current_user()),
):
    """Generate a new API key (max 20 per user). The raw key is returned ONCE only."""
    user_id = current_user["user_id"]
    store = _store()
    if len(store.list_api_keys(user_id)) >= _MAX_API_KEYS:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {_MAX_API_KEYS} API keys per user — delete some first",
        )

    from backend.utils.auth import generate_api_key, hash_api_key

    raw_key = generate_api_key()
    key_id = store.create_api_key(user_id=user_id, key_hash=hash_api_key(raw_key), name=req.name)
    return {
        "status": "created",
        "key_id": key_id,
        "key": raw_key,
        "name": req.name,
        "warning": "Save this key now — it will not be shown again.",
    }


@router.get("/api-keys")
async def list_api_keys(current_user: dict = Depends(_get_current_user())):
    """List all API keys for the authenticated user (ids and names only — no raw keys)."""
    keys = _store().list_api_keys(current_user["user_id"])
    return {"api_keys": keys, "count": len(keys)}


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: int,
    current_user: dict = Depends(_get_current_user()),
):
    """Revoke an API key by id."""
    if not _store().delete_api_key(key_id=key_id, user_id=current_user["user_id"]):
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "deleted", "key_id": key_id}
