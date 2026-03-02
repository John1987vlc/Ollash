"""
learning_router - migrated from learning_bp.py.
TODO: Migrate route logic from frontend/blueprints/learning_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/learning", tags=["learning"])


@router.get("/")
async def learning_index():
    """Index endpoint - implement from learning_bp.py."""
    return {"status": "ok", "router": "learning"}
