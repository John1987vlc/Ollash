"""
tuning_router - migrated from tuning_bp.py.
TODO: Migrate route logic from frontend/blueprints/tuning_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/tuning", tags=["tuning"])


@router.get("/")
async def tuning_index():
    """Index endpoint - implement from tuning_bp.py."""
    return {"status": "ok", "router": "tuning"}
