"""
pair_programming_router — migrated from pair_programming_bp.py.
TODO: Migrate route logic from frontend/blueprints/pair_programming_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/pair-programming", tags=["pair-programming"])


@router.get("/")
async def pair_programming_index():
    """Index endpoint — implement from pair_programming_bp.py."""
    return {"status": "ok", "router": "pair-programming"}
