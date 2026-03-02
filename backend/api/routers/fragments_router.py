"""
Fragments router — migrated from frontend/blueprints/fragments_bp.py.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.api.deps import service_error_handler
from backend.utils.core.memory.fragment_cache import FragmentCache
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.structured_logger import StructuredLogger

router = APIRouter(prefix="/api/fragments", tags=["fragments"])
logger = logging.getLogger(__name__)

_cache: FragmentCache | None = None


def _get_cache(request: Request) -> FragmentCache:
    """Lazily initialize the fragment cache from app state."""
    global _cache
    if _cache is None:
        root: Path = request.app.state.ollash_root_dir
        sl = StructuredLogger(root / "logs" / "fragments.log")
        _cache = FragmentCache(
            db_path=root / ".cache" / "fragments.db",
            logger=AgentLogger(sl, "fragments_api"),
        )
    return _cache


class FavoriteRequest(BaseModel):
    key: str
    favorite: bool = True


@router.get("")
@service_error_handler
async def list_fragments(request: Request):
    """List all cached fragments ordered by hits."""
    cache = _get_cache(request)
    rows = await cache.list_all()
    fragments = [
        {
            "key": row.get("key"),
            "type": row.get("fragment_type"),
            "language": row.get("language"),
            "content": row.get("content"),
            "hits": row.get("hits", 0),
            "favorite": row.get("metadata", {}).get("favorite", False),
        }
        for row in rows
    ]
    return {"fragments": fragments}


@router.post("/favorite")
@service_error_handler
async def favorite_fragment(body: FavoriteRequest, request: Request):
    """Toggle the favorite flag on a fragment."""
    cache = _get_cache(request)
    # Verify fragment exists
    all_rows = await cache.list_all()
    keys = {row.get("key") for row in all_rows}
    if body.key not in keys:
        raise HTTPException(status_code=404, detail="Fragment not found")

    await cache.set_favorite(body.key, body.favorite)
    return {"status": "success"}
