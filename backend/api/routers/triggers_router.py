"""
triggers_router - migrated from triggers_bp.py.
TODO: Migrate route logic from frontend/blueprints/triggers_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/triggers", tags=["triggers"])


@router.get("/")
async def triggers_index():
    """Index endpoint - implement from triggers_bp.py."""
    return {"status": "ok", "router": "triggers"}
