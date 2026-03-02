"""
insights_router — migrated from insights_bp.py.
TODO: Migrate route logic from frontend/blueprints/insights_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/insights", tags=["insights"])


@router.get("/")
async def insights_index():
    """Index endpoint — implement from insights_bp.py."""
    return {"status": "ok", "router": "insights"}
