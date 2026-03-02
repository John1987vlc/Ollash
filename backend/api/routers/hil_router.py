"""
hil_router — migrated from hil_bp.py.
TODO: Migrate route logic from frontend/blueprints/hil_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/hil", tags=["hil"])


@router.get("/")
async def hil_index():
    """Index endpoint — implement from hil_bp.py."""
    return {"status": "ok", "router": "hil"}
