"""
cybersecurity_router — migrated from cybersecurity_bp.py.
TODO: Migrate route logic from frontend/blueprints/cybersecurity_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/cybersecurity", tags=["cybersecurity"])


@router.get("/")
async def cybersecurity_index():
    """Index endpoint — implement from cybersecurity_bp.py."""
    return {"status": "ok", "router": "cybersecurity"}
