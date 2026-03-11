"""
git_router - migrated from git_views.py.
Handles git operations via API.
"""

import os
import subprocess
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/git", tags=["git"])


class GitCommitRequest(BaseModel):
    files: List[str]
    message: str


def run_git(args: List[str], cwd: Optional[str] = None):
    try:
        if cwd is None:
            cwd = os.getcwd()
        result = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True, check=False)
        return {"stdout": result.stdout, "stderr": result.stderr, "code": result.returncode}
    except Exception as e:
        return {"error": str(e)}


@router.get("/api/status")
async def get_status():
    status_res = run_git(["status", "--short"])
    branch_res = run_git(["rev-parse", "--abbrev-ref", "HEAD"])

    files = []
    if "stdout" in status_res and status_res["stdout"]:
        for line in status_res["stdout"].splitlines():
            if not line.strip():
                continue
            parts = line.strip().split()
            if len(parts) >= 2:
                files.append({"status": parts[0], "file": parts[1]})

    return {
        "branch": branch_res.get("stdout", "").strip() if "stdout" in branch_res else "unknown",
        "files": files,
        "clean": len(files) == 0,
    }


@router.get("/api/diff")
async def get_diff(file: str = Query(...)):
    diff = run_git(["diff", "HEAD", "--", file])
    return {"diff": diff.get("stdout", "") if "stdout" in diff else ""}


@router.post("/api/commit")
async def commit_changes(payload: GitCommitRequest):
    # Stage
    run_git(["add"] + payload.files)

    # Commit
    res = run_git(["commit", "-m", payload.message])

    if "code" in res and res["code"] == 0:
        return {"status": "success", "output": res.get("stdout")}

    error_msg = res.get("stderr") or res.get("error") or "Unknown error"
    raise HTTPException(status_code=500, detail=error_msg)


@router.get("/api/log")
async def get_log():
    log = run_git(["log", "-n", "5", "--pretty=format:%h - %s (%cr) <%an>"])
    return {"log": log.get("stdout", "").splitlines() if "stdout" in log else []}


@router.get("/")
async def git_index():
    return {"status": "ok", "router": "git"}
