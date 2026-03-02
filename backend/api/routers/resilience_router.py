"""
resilience_router - migrated from resilience_bp.py.
TODO: Migrate route logic from frontend/blueprints/resilience_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/resilience", tags=["resilience"])


@router.get("/")
async def resilience_index():
    """Index endpoint - implement from resilience_bp.py."""
    return {"status": "ok", "router": "resilience"}
