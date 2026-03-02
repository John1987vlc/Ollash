"""
sandbox_router - migrated from sandbox_bp.py.
TODO: Migrate route logic from frontend/blueprints/sandbox_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


@router.get("/")
async def sandbox_index():
    """Index endpoint - implement from sandbox_bp.py."""
    return {"status": "ok", "router": "sandbox"}
