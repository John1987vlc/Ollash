"""
prompt_studio_router - migrated from prompt_studio_bp.py.
TODO: Migrate route logic from frontend/blueprints/prompt_studio_bp.py
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/prompt-studio", tags=["prompt-studio"])


@router.get("/")
async def prompt_studio_index():
    """Index endpoint - implement from prompt_studio_bp.py."""
    return {"status": "ok", "router": "prompt-studio"}
