"""
multimodal_router — migrated from multimodal_bp.py.
TODO: Migrate route logic from frontend/blueprints/multimodal_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/multimodal", tags=["multimodal"])


@router.get("/")
async def multimodal_index():
    """Index endpoint — implement from multimodal_bp.py."""
    return {"status": "ok", "router": "multimodal"}
