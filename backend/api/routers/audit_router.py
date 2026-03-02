"""
audit_router — migrated from audit_bp.py.
TODO: Migrate route logic from frontend/blueprints/audit_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/")
async def audit_index():
    """Index endpoint — implement from audit_bp.py."""
    return {"status": "ok", "router": "audit"}
