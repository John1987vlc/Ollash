"""
operations_router - migrated from operations_bp.py.
TODO: Migrate route logic from frontend/blueprints/operations_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/operations", tags=["operations"])


@router.get("/")
async def operations_index():
    """Index endpoint - implement from operations_bp.py."""
    return {"status": "ok", "router": "operations"}
