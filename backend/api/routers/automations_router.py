"""
automations_router - migrated from automations_bp.py.
TODO: Migrate route logic from frontend/blueprints/automations_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/automations", tags=["automations"])


@router.get("/")
async def automations_index():
    """Index endpoint - implement from automations_bp.py."""
    return {"status": "ok", "router": "automations"}
