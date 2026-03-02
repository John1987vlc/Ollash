"""
Vite manifest reader for FastAPI.

Reads frontend/static/dist/.vite/manifest.json to resolve hashed asset URLs
when USE_VITE_ASSETS=true. Falls back to direct /static/... paths in dev mode.

Usage in Jinja2 templates (via template global):
    {{ asset_url('js/index.ts') }}  →  /static/dist/js/index-abc123.js

Register in app.py:
    templates.env.globals["asset_url"] = asset_url
    templates.env.globals["use_vite"] = os.getenv("USE_VITE_ASSETS", "false").lower() == "true"
"""

import json
import os
from functools import lru_cache
from pathlib import Path

_MANIFEST_PATH = Path("frontend/static/dist/.vite/manifest.json")
_USE_VITE = os.getenv("USE_VITE_ASSETS", "false").lower() == "true"


@lru_cache(maxsize=1)
def _load_manifest() -> dict:
    """Load and cache the Vite manifest (invalidated on process restart)."""
    if not _MANIFEST_PATH.exists():
        return {}
    return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))


def asset_url(name: str) -> str:
    """
    Return the URL for a Vite-managed asset.

    In production (USE_VITE_ASSETS=true): resolves via manifest to the
    hashed filename (e.g., /static/dist/js/index-abc123.js).

    In development: returns the direct static path (/static/js/...).

    Args:
        name: Asset path relative to frontend/static/ (e.g. 'js/index.js').

    Returns:
        URL string suitable for use in <script src="..."> or <link href="...">.
    """
    if not _USE_VITE:
        return f"/static/{name}"

    manifest = _load_manifest()
    entry = manifest.get(name, {})
    file_path = entry.get("file", name)
    return f"/static/dist/{file_path}"
