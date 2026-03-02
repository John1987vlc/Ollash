"""
plugins_router - migrated from plugins_bp.py.
TODO: Migrate route logic from frontend/blueprints/plugins_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


@router.get("/")
async def plugins_index():
    """Index endpoint - implement from plugins_bp.py."""
    return {"status": "ok", "router": "plugins"}
