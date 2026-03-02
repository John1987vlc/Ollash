"""
refactor_router — migrated from refactor_bp.py.
TODO: Migrate route logic from frontend/blueprints/refactor_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/refactor", tags=["refactor"])


@router.get("/")
async def refactor_index():
    """Index endpoint — implement from refactor_bp.py."""
    return {"status": "ok", "router": "refactor"}
