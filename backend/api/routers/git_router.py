"""
Git router — migrated from frontend/blueprints/git_views.py.
"""

import asyncio
import logging
import os
import subprocess
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from backend.api.deps import service_error_handler
from frontend.schemas.git_schemas import GitCommitRequest

router = APIRouter(prefix="/api/git", tags=["git"])
logger = logging.getLogger(__name__)


def _run_git(args: List[str], cwd: Optional[str] = None) -> Dict[str, Any]:
    """Run a git command and return stdout/stderr/code."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd or os.getcwd(),
            capture_output=True,
            text=True,
            check=False,
        )
        return {"stdout": result.stdout, "stderr": result.stderr, "code": result.returncode}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/status")
@service_error_handler
async def get_status():
    """Return current git status (branch + changed files)."""
    status, branch = await asyncio.gather(
        asyncio.to_thread(_run_git, ["status", "--short"]),
        asyncio.to_thread(_run_git, ["rev-parse", "--abbrev-ref", "HEAD"]),
    )
    files = []
    if status.get("stdout"):
        for line in status["stdout"].splitlines():
            if not line.strip():
                continue
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                files.append({"status": parts[0], "file": parts[1]})
    return {
        "branch": branch.get("stdout", "").strip(),
        "files": files,
        "clean": len(files) == 0,
    }


@router.get("/diff")
@service_error_handler
async def get_diff(file: str):
    """Return the git diff for a single file."""
    if not file:
        raise HTTPException(status_code=400, detail="No file specified")
    diff = await asyncio.to_thread(_run_git, ["diff", "HEAD", "--", file])
    return {"diff": diff.get("stdout", "")}


@router.post("/commit")
@service_error_handler
async def commit_changes(body: GitCommitRequest):
    """Stage files and create a commit."""
    await asyncio.to_thread(_run_git, ["add"] + body.files)
    res = await asyncio.to_thread(_run_git, ["commit", "-m", body.message])
    if res.get("code") == 0:
        return {"status": "success", "output": res.get("stdout")}
    raise HTTPException(status_code=500, detail=res.get("stderr", "Commit failed"))


@router.get("/log")
@service_error_handler
async def get_log():
    """Return the last 5 commit log entries."""
    log = await asyncio.to_thread(
        _run_git, ["log", "-n", "5", "--pretty=format:%h - %s (%cr) <%an>"]
    )
    return {"log": log.get("stdout", "").splitlines()}
