"""Models router — manage Ollama models (list, pull, delete, unload)."""

from __future__ import annotations

import json
from typing import Any

import requests
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.core.config import config as app_config

router = APIRouter(prefix="/api/models", tags=["models"])


_OLLAMA_ALLOWED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _ollama_url() -> str:
    """Return the configured Ollama base URL, validated against an allowlist.

    Extra hosts can be whitelisted via the OLLAMA_HOSTS_ALLOWLIST env var
    (comma-separated). This prevents SSRF via a compromised config file.
    """
    import os

    url = str(app_config.get("ollama_url", "http://localhost:11434")).rstrip("/")
    parsed = urlparse(url)
    extra = {h.strip() for h in os.environ.get("OLLAMA_HOSTS_ALLOWLIST", "").split(",") if h.strip()}
    allowed = _OLLAMA_ALLOWED_HOSTS | extra
    if parsed.hostname not in allowed:
        raise HTTPException(
            status_code=500,
            detail=f"Ollama host '{parsed.hostname}' is not in the allowlist.",
        )
    return url


class PullRequest(BaseModel):
    name: str


class DeleteRequest(BaseModel):
    name: str


class UnloadRequest(BaseModel):
    name: str | None = None


@router.get("/")
async def list_models():
    """List all locally available Ollama models."""
    url = _ollama_url()
    try:
        resp = requests.get(f"{url}/api/tags", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        models = data.get("models", [])
        return {
            "models": [
                {
                    "name": m.get("name"),
                    "size_mb": round(m.get("size", 0) / 1_048_576),
                    "modified_at": m.get("modified_at"),
                    "digest": m.get("digest", "")[:12],
                    "details": m.get("details", {}),
                }
                for m in models
            ],
            "count": len(models),
        }
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Cannot connect to Ollama")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/running")
async def list_running_models():
    """List models currently loaded in VRAM (Ollama /api/ps)."""
    url = _ollama_url()
    try:
        resp = requests.get(f"{url}/api/ps", timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return {"running": data.get("models", [])}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pull")
async def pull_model(req: PullRequest):
    """Pull a model from Ollama registry with SSE progress streaming."""
    url = _ollama_url()

    async def _generate():
        try:
            with requests.post(
                f"{url}/api/pull",
                json={"name": req.name, "stream": True},
                stream=True,
                timeout=3600,
            ) as resp:
                for line in resp.iter_lines():
                    if line:
                        try:
                            data: dict[str, Any] = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        yield f"data: {json.dumps(data)}\n\n"
                        if data.get("status") == "success":
                            break
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(_generate(), media_type="text/event-stream")


@router.delete("/")
async def delete_model(req: DeleteRequest):
    """Delete a locally stored Ollama model."""
    url = _ollama_url()
    try:
        resp = requests.delete(f"{url}/api/delete", json={"name": req.name}, timeout=30)
        if resp.status_code == 200:
            return {"status": "deleted", "name": req.name}
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unload")
async def unload_model(req: UnloadRequest):
    """Unload a model from VRAM (keep_alive=0)."""
    url = _ollama_url()
    model = req.name
    if not model:
        # Unload all running models
        try:
            resp = requests.get(f"{url}/api/ps", timeout=5)
            running = resp.json().get("models", []) if resp.ok else []
            unloaded = []
            for m in running:
                name = m.get("name", "")
                requests.post(f"{url}/api/generate", json={"model": name, "keep_alive": 0}, timeout=10)
                unloaded.append(name)
            return {"status": "unloaded", "models": unloaded}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    try:
        requests.post(f"{url}/api/generate", json={"model": model, "keep_alive": 0}, timeout=10)
        return {"status": "unloaded", "name": model}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{name}/info")
async def model_info(name: str):
    """Show detailed info for a model."""
    url = _ollama_url()
    try:
        resp = requests.post(f"{url}/api/show", json={"name": name}, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
