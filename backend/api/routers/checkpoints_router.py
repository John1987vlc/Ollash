"""
Checkpoints router — migrated from frontend/blueprints/checkpoints_bp.py.
"""

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.api.deps import service_error_handler
from backend.utils.core.io.checkpoint_manager import CheckpointManager
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.structured_logger import StructuredLogger

router = APIRouter(prefix="/api/checkpoints", tags=["checkpoints"])
logger = logging.getLogger(__name__)


def _get_checkpoint_manager(request: Request) -> CheckpointManager:
    """Build a CheckpointManager from app state."""
    root: Path = request.app.state.ollash_root_dir
    sl = StructuredLogger(root / "logs" / "checkpoints.log")
    return CheckpointManager(
        root / ".ollash" / "checkpoints",
        AgentLogger(sl, "checkpoints_api"),
    )


class RestoreRequest(BaseModel):
    project_name: str
    phase_name: str


@router.get("/{project_name}")
@service_error_handler
async def list_checkpoints(project_name: str, request: Request):
    """List all checkpoints for a project."""
    mgr = _get_checkpoint_manager(request)
    checkpoints = await mgr.list_checkpoints(project_name)
    return {"checkpoints": checkpoints}


@router.post("/restore")
@service_error_handler
async def restore_checkpoint(body: RestoreRequest, request: Request):
    """Restore files from a saved checkpoint."""
    root: Path = request.app.state.ollash_root_dir
    mgr = _get_checkpoint_manager(request)

    checkpoint = await mgr.load_at_phase(body.project_name, body.phase_name)
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    project_dir = root / "generated_projects" / "auto_agent_projects" / body.project_name

    def _restore_files() -> None:
        for path, content in checkpoint.generated_files.items():
            full_path = project_dir / path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

    await asyncio.to_thread(_restore_files)
    return {"status": "restored"}
