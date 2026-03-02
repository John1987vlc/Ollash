"""
common_router - migrated from common_bp.py.
TODO: Migrate route logic from frontend/blueprints/common_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/common", tags=["common"])


@router.get("/")
async def common_index():
    """Index endpoint - implement from common_bp.py."""
    return {"status": "ok", "router": "common"}
