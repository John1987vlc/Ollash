"""Local auth utilities — JWT tokens, PBKDF2 passwords, API key generation.

Uses werkzeug.security (PBKDF2-SHA256) for password hashing — already a
project dependency and avoids the passlib/bcrypt version incompatibility.

All secrets live in environment variables or are generated fresh on startup
(suitable for single-node local deployment).  Nothing is sent externally.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt  # noqa: F401  (JWTError re-exported for callers)
from werkzeug.security import check_password_hash, generate_password_hash

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Override via OLLASH_SECRET_KEY env var in production.
# A fresh random key is generated each startup when the env var is absent —
# this invalidates tokens on restart, which is fine for a local tool.
SECRET_KEY: str = os.environ.get("OLLASH_SECRET_KEY", secrets.token_hex(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.environ.get("OLLASH_JWT_EXPIRE_HOURS", "24"))

# ---------------------------------------------------------------------------
# Password helpers  (PBKDF2-SHA256 via werkzeug, no extra deps)
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Return a PBKDF2-SHA256 hash of *plain* text password."""
    return generate_password_hash(plain, method="pbkdf2:sha256", salt_length=16)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    return check_password_hash(hashed, plain)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def create_access_token(user_id: int, username: str) -> str:
    """Create a signed JWT access token with *user_id* and *username* claims."""
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": str(user_id), "username": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT token, returning the payload dict.

    Raises ``jose.JWTError`` on invalid / expired tokens.
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ---------------------------------------------------------------------------
# API key helpers
# ---------------------------------------------------------------------------


def generate_api_key() -> str:
    """Generate a random, URL-safe API key string."""
    return f"ollash_{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str) -> str:
    """One-way SHA-256 hash of a raw API key (stored, never the raw value)."""
    return hashlib.sha256(raw_key.encode()).hexdigest()
