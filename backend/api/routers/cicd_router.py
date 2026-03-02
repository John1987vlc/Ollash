"""
cicd_router - migrated from cicd_bp.py.
TODO: Migrate route logic from frontend/blueprints/cicd_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/cicd", tags=["cicd"])


@router.get("/")
async def cicd_index():
    """Index endpoint - implement from cicd_bp.py."""
    return {"status": "ok", "router": "cicd"}
