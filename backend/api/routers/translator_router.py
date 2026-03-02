"""
translator_router — migrated from translator_bp.py.
TODO: Migrate route logic from frontend/blueprints/translator_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/translator", tags=["translator"])


@router.get("/")
async def translator_index():
    """Index endpoint — implement from translator_bp.py."""
    return {"status": "ok", "router": "translator"}
