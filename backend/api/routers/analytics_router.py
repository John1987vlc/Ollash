"""
analytics_router - migrated from analytics_bp.py.
TODO: Migrate route logic from frontend/blueprints/analytics_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/")
async def analytics_index():
    """Index endpoint - implement from analytics_bp.py."""
    return {"status": "ok", "router": "analytics"}
