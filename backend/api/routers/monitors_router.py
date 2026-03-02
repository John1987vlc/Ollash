"""
monitors_router - migrated from monitors_bp.py.
TODO: Migrate route logic from frontend/blueprints/monitors_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/monitors", tags=["monitors"])


@router.get("/")
async def monitors_index():
    """Index endpoint - implement from monitors_bp.py."""
    return {"status": "ok", "router": "monitors"}
