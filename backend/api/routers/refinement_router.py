"""
refinement_router - migrated from refinement_bp.py.
TODO: Migrate route logic from frontend/blueprints/refinement_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/refinement", tags=["refinement"])


@router.get("/")
async def refinement_index():
    """Index endpoint - implement from refinement_bp.py."""
    return {"status": "ok", "router": "refinement"}
