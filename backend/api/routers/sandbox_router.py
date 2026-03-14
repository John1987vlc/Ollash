"""Sandbox router — execute code securely in a subprocess."""

from __future__ import annotations

import asyncio
import sys
import tempfile
import time
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])

# Languages supported and how to run them
_RUNNERS: dict[str, list[str]] = {
    "python": [sys.executable],
    "javascript": ["node"],
    "js": ["node"],
    "bash": ["bash"],
    "sh": ["sh"],
}
_EXT: dict[str, str] = {
    "python": ".py",
    "javascript": ".js",
    "js": ".js",
    "bash": ".sh",
    "sh": ".sh",
}
_TIMEOUT_DEFAULT = 30
_TIMEOUT_MAX = 120


class ExecuteRequest(BaseModel):
    code: str
    language: Literal["python", "javascript", "js", "bash", "sh"] = "python"
    timeout: int = _TIMEOUT_DEFAULT
    working_dir: str | None = None


@router.get("/")
async def sandbox_index():
    return {"status": "ok", "supported_languages": list(_RUNNERS.keys())}


@router.post("/execute")
async def execute_code(req: ExecuteRequest):
    """Execute code and return stdout/stderr/exit_code synchronously."""
    lang = req.language.lower()
    runner = _RUNNERS.get(lang)
    if not runner:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {lang}")

    timeout = min(req.timeout, _TIMEOUT_MAX)
    ext = _EXT.get(lang, ".tmp")

    with tempfile.NamedTemporaryFile(suffix=ext, mode="w", delete=False, encoding="utf-8") as f:
        f.write(req.code)
        tmp_path = f.name

    start = time.monotonic()
    try:
        proc = await asyncio.create_subprocess_exec(
            *runner,
            tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=req.working_dir,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {
                "stdout": "",
                "stderr": f"Execution timed out after {timeout}s",
                "exit_code": -1,
                "duration_ms": round((time.monotonic() - start) * 1000),
                "timed_out": True,
            }
        return {
            "stdout": stdout_bytes.decode("utf-8", errors="replace"),
            "stderr": stderr_bytes.decode("utf-8", errors="replace"),
            "exit_code": proc.returncode,
            "duration_ms": round((time.monotonic() - start) * 1000),
            "timed_out": False,
        }
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass


@router.post("/execute/stream")
async def execute_code_stream(req: ExecuteRequest):
    """Execute code and stream stdout/stderr as SSE."""
    lang = req.language.lower()
    runner = _RUNNERS.get(lang)
    if not runner:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {lang}")

    timeout = min(req.timeout, _TIMEOUT_MAX)
    ext = _EXT.get(lang, ".tmp")

    with tempfile.NamedTemporaryFile(suffix=ext, mode="w", delete=False, encoding="utf-8") as f:
        f.write(req.code)
        tmp_path = f.name

    async def _generate():
        import json

        proc = await asyncio.create_subprocess_exec(
            *runner,
            tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=req.working_dir,
        )
        start = time.monotonic()

        async def _read_stream(stream, kind: str):
            if stream is None:
                return
            async for line in stream:
                text = line.decode("utf-8", errors="replace").rstrip("\n")
                yield f"data: {json.dumps({'type': kind, 'line': text})}\n\n"

        async def _merge():
            # Read stdout and stderr concurrently
            stdout_gen = _read_stream(proc.stdout, "stdout")
            stderr_gen = _read_stream(proc.stderr, "stderr")
            # Simple sequential drain (subprocess buffers them separately)
            async for chunk in stdout_gen:
                yield chunk
            async for chunk in stderr_gen:
                yield chunk

        try:
            async for chunk in _merge():
                yield chunk
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            yield f"data: {json.dumps({'type': 'error', 'line': f'Timed out after {timeout}s'})}\n\n"
        finally:
            duration = round((time.monotonic() - start) * 1000)
            yield f"data: {json.dumps({'type': 'done', 'exit_code': proc.returncode, 'duration_ms': duration})}\n\n"
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass

    return StreamingResponse(_generate(), media_type="text/event-stream")
