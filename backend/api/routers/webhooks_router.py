"""
webhooks_router - migrated from webhooks_bp.py.
TODO: Migrate route logic from frontend/blueprints/webhooks_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.get("/")
async def webhooks_index():
    """Index endpoint - implement from webhooks_bp.py."""
    return {"status": "ok", "router": "webhooks"}
