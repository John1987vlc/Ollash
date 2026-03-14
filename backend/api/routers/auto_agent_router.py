"""
Auto Agent router — migrated from auto_agent_bp.py (999 lines).

Long-running 22-phase pipeline runs as background tasks.
SSE uses StreamingResponse with async generator.
Security patterns preserved: path traversal protection, magic byte validation,
subprocess shell=False, git URL validation.
"""

import asyncio
import io
import os
import re
import shlex
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.core.containers import main_container

router = APIRouter(tags=["auto_agent"])

_SAFE_FILENAME_RE = re.compile(r"[^\w\-.]")
_IMAGE_MAGIC: Dict[bytes, str] = {
    b"\x89PNG": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
    b"GIF8": "image/gif",
    b"RIFF": "image/webp",
}


# ---------------------------------------------------------------------------
# Security helpers (preserved from Flask blueprint)
# ---------------------------------------------------------------------------


def _safe_resolve(base: Path, relative: str) -> Path:
    """Resolve relative path and verify it stays within base (path traversal protection)."""
    resolved = (base / relative).resolve()
    if not resolved.is_relative_to(base.resolve()):
        raise ValueError(f"Path traversal attempt: '{relative}'")
    return resolved


def _validate_image_magic(data: bytes) -> bool:
    """Validate image by magic bytes, not by client-supplied MIME type."""
    header = data[:12]
    for magic in _IMAGE_MAGIC:
        if header.startswith(magic):
            if magic == b"RIFF":
                return header[8:12] == b"WEBP"
            return True
    return False


# ---------------------------------------------------------------------------
# Project creation & streaming
# ---------------------------------------------------------------------------


_PROJECT_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,80}$")


class ProjectCreateRequest(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_\-]+$")
    project_description: str = Field(..., min_length=1, max_length=20000)
    git_push: bool = False
    git_token: str = Field(default="", max_length=200)
    maintenance_enabled: bool = False
    use_rag: bool = False
    target_language: str = Field(default="", max_length=50)
    preferred_stack: str = Field(default="", max_length=200)
    resume_from_phase: Optional[int] = Field(default=None, ge=0, le=50)
    # Extended fields from the wizard
    template_name: Optional[str] = Field(default=None, max_length=100)
    python_version: Optional[str] = Field(default=None, max_length=20)
    license_type: Optional[str] = Field(default=None, max_length=50)
    include_docker: bool = False
    include_terraform: bool = False
    num_refine_loops: int = Field(default=1, ge=1, le=10)
    git_auto_create: bool = False
    git_repo_url: str = Field(default="", max_length=500)
    maintenance_interval: Optional[int] = Field(default=None, ge=1, le=1440)
    pool_size: Optional[int] = Field(default=None, ge=1, le=20)
    timeout: Optional[int] = Field(default=None, ge=30, le=7200)
    parallel_generation_enabled: bool = False
    security_scanning_enabled: bool = False
    block_security_critical: bool = False
    checkpoint_enabled: bool = False
    cost_tracking_enabled: bool = False
    senior_review_as_pr: bool = False
    enable_github_wiki: bool = False
    enable_github_pages: bool = False
    feature_flags: Dict[str, bool] = {}


@router.post("/api/projects/create")
async def create_project(
    request: Request,
    background_tasks: BackgroundTasks,
    body: ProjectCreateRequest,
):
    """
    Start the 22-phase AutoAgent pipeline as a background task.
    Returns immediately with session info; progress streamed via /api/projects/stream/{name}.
    """
    event_publisher = request.app.state.event_publisher
    chat_event_bridge = request.app.state.chat_event_bridge

    # Extract fields from body for easier access or pass as dict
    params = body.model_dump()
    project_description = params.pop("project_description")
    project_name = params.pop("project_name")

    async def _run_agent():
        try:
            agent = main_container.auto_agent_module.auto_agent()
            agent.event_publisher = event_publisher
            await asyncio.to_thread(
                agent.run,
                project_description,
                project_name,
                **params,
            )
            chat_event_bridge.push_event("stream_end", {"message": f"Project '{project_name}' generated."})
        except Exception as exc:
            logger = main_container.core.logging.logger()
            logger.error(f"AutoAgent error: {exc}", exc_info=True)
            chat_event_bridge.push_event("error", {"message": str(exc)})

    background_tasks.add_task(_run_agent)
    return {"status": "started", "project_name": project_name}


@router.get("/api/projects/stream/{project_name}")
async def stream_project_logs(project_name: str, request: Request):
    """SSE stream for real-time project generation logs."""
    chat_event_bridge = request.app.state.chat_event_bridge
    loop = asyncio.get_event_loop()

    async def _gen() -> AsyncIterator[str]:
        it = iter(chat_event_bridge.iter_events())
        while True:
            try:
                chunk = await loop.run_in_executor(None, next, it)
                yield chunk
            except StopIteration:
                break

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# File operations
# ---------------------------------------------------------------------------


class FilePathRequest(BaseModel):
    file_path_relative: str = Field(..., min_length=1, max_length=500)


class FileSaveRequest(BaseModel):
    file_path_relative: str = Field(..., min_length=1, max_length=500)
    content: str = Field(default="", max_length=10 * 1024 * 1024)  # 10 MB cap


@router.post("/api/projects/{project_name}/file")
async def read_file_content(
    project_name: str,
    body: FilePathRequest,
    request: Request,
):
    ollash_root_dir = request.app.state.ollash_root_dir
    project_base = ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name

    try:
        full_path = _safe_resolve(project_base, body.file_path_relative)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path.")

    if not full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        content = full_path.read_text(encoding="utf-8")
        return {"status": "success", "content": content, "type": "text"}
    except UnicodeDecodeError:
        return {"status": "success", "content": "[Binary file]", "type": "binary"}


@router.put("/api/projects/{project_name}/file")
async def save_file_content(
    project_name: str,
    body: FileSaveRequest,
    request: Request,
):
    ollash_root_dir = request.app.state.ollash_root_dir
    project_base = ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name

    try:
        full_path = _safe_resolve(project_base, body.file_path_relative)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path.")

    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(body.content, encoding="utf-8")
    return {"status": "success"}


# ---------------------------------------------------------------------------
# Image upload
# ---------------------------------------------------------------------------


@router.post("/api/projects/images/upload")
async def upload_context_images(
    files: List[UploadFile] = File(...),
    request: Request = None,
):
    ollash_root_dir = request.app.state.ollash_root_dir
    upload_dir = ollash_root_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    allowed_mimes = {"image/png", "image/jpeg", "image/gif", "image/webp"}
    saved = []

    for uploaded_file in files:
        if uploaded_file.content_type not in allowed_mimes:
            raise HTTPException(status_code=400, detail=f"Unsupported MIME: {uploaded_file.content_type}")
        data = await uploaded_file.read()
        if not _validate_image_magic(data):
            raise HTTPException(status_code=400, detail="File content doesn't match declared MIME type.")
        safe_name = _SAFE_FILENAME_RE.sub("_", uploaded_file.filename or "image")
        dest = upload_dir / safe_name
        dest.write_bytes(data)
        saved.append(str(dest))

    return {"status": "ok", "paths": saved}


# ---------------------------------------------------------------------------
# Command execution
# ---------------------------------------------------------------------------


class CommandRequest(BaseModel):
    command: str


@router.post("/api/projects/{project_name}/execute_command")
async def execute_command(project_name: str, body: CommandRequest, request: Request):
    ollash_root_dir = request.app.state.ollash_root_dir
    project_base = ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name

    if not project_base.is_dir():
        raise HTTPException(status_code=404, detail="Project not found.")

    try:
        cmd_list = shlex.split(body.command) if isinstance(body.command, str) else body.command
        result = subprocess.run(
            cmd_list,
            shell=False,  # CRITICAL: prevents shell injection
            capture_output=True,
            text=True,
            cwd=project_base,
            check=False,
            timeout=300,
        )
        return {
            "status": "success",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Command timed out.")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Clone repository
# ---------------------------------------------------------------------------


class CloneRequest(BaseModel):
    git_url: str
    project_name: Optional[str] = None


@router.post("/api/projects/clone")
async def clone_project(body: CloneRequest, request: Request):
    from backend.utils.core.analysis.input_validators import validate_git_url, validate_project_name

    if not validate_git_url(body.git_url):
        raise HTTPException(status_code=400, detail="Invalid git URL.")

    project_name = body.project_name or body.git_url.split("/")[-1].replace(".git", "")
    if not validate_project_name(project_name):
        raise HTTPException(status_code=400, detail="Invalid project name.")

    ollash_root_dir = request.app.state.ollash_root_dir
    projects_dir = ollash_root_dir / "generated_projects" / "auto_agent_projects"
    target = projects_dir / project_name

    if target.exists():
        raise HTTPException(status_code=409, detail="Project already exists.")

    projects_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["git", "clone", body.git_url, str(target)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Clone failed: {result.stderr.strip()}")
        return {"status": "success", "project_name": project_name}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Clone timed out (5 min limit).")


# ---------------------------------------------------------------------------
# Export to ZIP
# ---------------------------------------------------------------------------


@router.get("/api/projects/{project_name}/export")
async def export_project_zip(project_name: str, request: Request):
    ollash_root_dir = request.app.state.ollash_root_dir
    project_path = ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name

    if not project_path.is_dir():
        raise HTTPException(status_code=404, detail="Project not found.")

    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv"}
    memory_file = io.BytesIO()

    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for f in files:
                if f.startswith(".") or f.endswith(".pyc"):
                    continue
                full_path = os.path.join(root, f)
                arcname = os.path.relpath(full_path, project_path)
                zf.write(full_path, arcname)

    memory_file.seek(0)

    from fastapi.responses import Response

    return Response(
        content=memory_file.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={project_name}.zip"},
    )


# ---------------------------------------------------------------------------
# Project listing and deletion
# ---------------------------------------------------------------------------


@router.get("/api/projects/list")
@router.get("/api/projects")
async def list_projects(request: Request):
    ollash_root_dir = request.app.state.ollash_root_dir
    projects_dir = ollash_root_dir / "generated_projects" / "auto_agent_projects"
    projects = []
    if projects_dir.exists():
        for p in sorted(projects_dir.iterdir()):
            if p.is_dir():
                projects.append(
                    {
                        "name": p.name,
                        "path": str(p),
                        "modified": p.stat().st_mtime,
                    }
                )
    return {"projects": projects}


@router.delete("/api/projects/{project_name}")
async def delete_project(project_name: str, request: Request):
    ollash_root_dir = request.app.state.ollash_root_dir
    project_path = ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name

    if not project_path.exists():
        raise HTTPException(status_code=404, detail="Project not found.")

    shutil.rmtree(project_path)
    return {"status": "deleted", "project_name": project_name}


# ---------------------------------------------------------------------------
# Resume from checkpoint
# ---------------------------------------------------------------------------


@router.post("/api/projects/{project_name}/resume")
async def resume_project(project_name: str, background_tasks: BackgroundTasks, request: Request):
    event_publisher = request.app.state.event_publisher

    async def _run_resume():
        from backend.agents.domain_agent_orchestrator import DomainAgentOrchestrator

        orch: DomainAgentOrchestrator = main_container.domain_agents.orchestrator()
        orch.event_publisher = event_publisher
        await orch.resume(project_name)

    background_tasks.add_task(_run_resume)
    return {"status": "started"}


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------


@router.get("/api/projects/{project_name}/checkpoint")
async def get_checkpoint(project_name: str, request: Request):
    from backend.utils.core.io.checkpoint_manager import CheckpointManager

    ollash_root_dir = request.app.state.ollash_root_dir
    cm = CheckpointManager(ollash_root_dir / ".ollash" / "checkpoints", logger=None)
    data = cm.load_dag(project_name)
    if not data:
        raise HTTPException(status_code=404, detail="No checkpoint found.")
    return {"project_name": project_name, "timestamp": data.get("timestamp"), "data": data}


# ---------------------------------------------------------------------------
# Git status
# ---------------------------------------------------------------------------


@router.get("/api/projects/{project_name}/git_status")
async def get_project_git_status(project_name: str, request: Request):
    ollash_root_dir = request.app.state.ollash_root_dir
    project_path = ollash_root_dir / "generated_projects" / "auto_agent_projects" / project_name
    if not project_path.is_dir():
        raise HTTPException(status_code=404, detail="Project not found.")
    try:
        from backend.utils.domains.git.git_pr_tool import GitPRTool

        logger = main_container.core.logging.logger()
        git_tool = GitPRTool(str(project_path), logger)
        prs = git_tool.list_open_prs()
        return {"status": "success", "git_enabled": True, "prs": prs}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
