"""
export_router - migrated from export_bp.py.
TODO: Migrate route logic from frontend/blueprints/export_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/")
async def export_index():
    """Index endpoint - implement from export_bp.py."""
    return {"status": "ok", "router": "export"}
