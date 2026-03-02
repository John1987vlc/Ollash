"""
knowledge_router - migrated from knowledge_bp.py.
TODO: Migrate route logic from frontend/blueprints/knowledge_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/")
async def knowledge_index():
    """Index endpoint - implement from knowledge_bp.py."""
    return {"status": "ok", "router": "knowledge"}
