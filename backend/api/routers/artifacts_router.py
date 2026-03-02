"""
artifacts_router — migrated from artifacts_bp.py.
TODO: Migrate route logic from frontend/blueprints/artifacts_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


@router.get("/")
async def artifacts_index():
    """Index endpoint — implement from artifacts_bp.py."""
    return {"status": "ok", "router": "artifacts"}
