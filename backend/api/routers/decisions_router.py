"""
decisions_router - migrated from decisions_bp.py.
TODO: Migrate route logic from frontend/blueprints/decisions_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/decisions", tags=["decisions"])


@router.get("/")
async def decisions_index():
    """Index endpoint - implement from decisions_bp.py."""
    return {"status": "ok", "router": "decisions"}
