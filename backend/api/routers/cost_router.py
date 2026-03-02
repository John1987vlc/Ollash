"""
cost_router — migrated from cost_bp.py.
TODO: Migrate route logic from frontend/blueprints/cost_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/cost", tags=["cost"])


@router.get("/")
async def cost_index():
    """Index endpoint — implement from cost_bp.py."""
    return {"status": "ok", "router": "cost"}
