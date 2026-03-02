"""
analysis_router — migrated from analysis_bp.py.
TODO: Migrate route logic from frontend/blueprints/analysis_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/")
async def analysis_index():
    """Index endpoint — implement from analysis_bp.py."""
    return {"status": "ok", "router": "analysis"}
