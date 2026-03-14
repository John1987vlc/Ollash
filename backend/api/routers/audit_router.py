"""Audit router — LLM call log, security scan, code review."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/audit", tags=["audit"])


class ScanRequest(BaseModel):
    path: str


class ReviewRequest(BaseModel):
    code: str
    file_path: str = "snippet.py"


@router.get("/")
async def audit_index():
    return {"status": "ok", "endpoints": ["/llm", "/scan", "/review"]}


@router.get("/llm")
async def get_llm_audit_log(limit: int = 100):
    """Return recent LLM calls for audit purposes."""
    from backend.utils.core.llm.call_log import llm_call_log

    entries = llm_call_log.get_recent(limit=limit)
    stats = llm_call_log.stats()
    return {"entries": entries, "stats": stats, "count": len(entries)}


@router.post("/scan")
async def security_scan(req: ScanRequest):
    """Run a quick security scan on the given path using the vulnerability scanner."""
    target = Path(req.path)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {req.path}")

    try:
        from backend.core.containers import main_container

        scanner = main_container.core.analysis.vulnerability_scanner()

        if hasattr(scanner, "scan_path"):
            result = await asyncio.get_event_loop().run_in_executor(None, scanner.scan_path, str(target))
        elif hasattr(scanner, "scan"):
            result = await asyncio.get_event_loop().run_in_executor(None, scanner.scan, str(target))
        else:
            result = {"note": "Scanner has no scan_path/scan method", "path": str(target)}
        return {"status": "ok", "path": str(target), "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review")
async def code_review(req: ReviewRequest):
    """Ask the senior reviewer LLM to review a code snippet."""
    try:
        from backend.core.containers import main_container

        llm_manager = main_container.auto_agent_module.llm_client_manager()
        client = llm_manager.get_client("senior_reviewer")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior software engineer performing a code review. "
                    "Identify bugs, security issues, performance problems, and code quality issues. "
                    "Be concise and actionable."
                ),
            },
            {
                "role": "user",
                "content": f"Review this code from `{req.file_path}`:\n\n```\n{req.code[:8000]}\n```",
            },
        ]

        result, usage = await asyncio.wait_for(
            client.achat(messages),
            timeout=120,
        )
        return {
            "review": result.get("content", ""),
            "tokens": usage,
            "file_path": req.file_path,
        }
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Review timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
