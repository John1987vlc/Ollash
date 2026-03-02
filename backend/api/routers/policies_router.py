"""
policies_router — migrated from policies_bp.py.
TODO: Migrate route logic from frontend/blueprints/policies_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/policies", tags=["policies"])


@router.get("/")
async def policies_index():
    """Index endpoint — implement from policies_bp.py."""
    return {"status": "ok", "router": "policies"}
