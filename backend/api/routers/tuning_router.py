"""Tuning router — create custom Ollama Modelfiles, list and delete fine-tuned models."""

from __future__ import annotations

import os

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/tuning", tags=["tuning"])

_OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")


def _ollama_url() -> str:
    return os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")


class CreateModelRequest(BaseModel):
    name: str
    base_model: str
    system_prompt: str = ""
    temperature: float = 0.4
    context_window: int = 4096
    extra_modelfile: str = ""


class DeleteModelRequest(BaseModel):
    name: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
async def tuning_index():
    return {"status": "ok", "endpoints": ["/create", "/templates", "/delete"]}


@router.get("/templates")
async def list_templates():
    """Return a list of available base models from Ollama that can be used as tuning bases."""
    try:
        resp = requests.get(f"{_ollama_url()}/api/tags", timeout=10)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        return {"status": "ok", "base_models": models}
    except (requests.ConnectionError, requests.Timeout):
        raise HTTPException(status_code=503, detail="Cannot reach Ollama")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create")
async def create_custom_model(req: CreateModelRequest):
    """Create a custom model via Ollama /api/create using a generated Modelfile.

    The Modelfile sets the base model, an optional system prompt, temperature and
    context window via PARAMETER directives.
    """
    lines = [f"FROM {req.base_model}"]

    if req.system_prompt.strip():
        escaped = req.system_prompt.replace('"', '\\"')
        lines.append(f'SYSTEM """{escaped}"""')

    lines.append(f"PARAMETER temperature {req.temperature}")
    lines.append(f"PARAMETER num_ctx {req.context_window}")

    if req.extra_modelfile.strip():
        lines.append(req.extra_modelfile.strip())

    modelfile = "\n".join(lines)

    payload = {"name": req.name, "modelfile": modelfile}

    try:
        resp = requests.post(
            f"{_ollama_url()}/api/create",
            json=payload,
            timeout=300,
            stream=False,
        )
        resp.raise_for_status()
        # Ollama streams newline-delimited JSON; last line has "status":"success"
        last_status = ""
        for line in resp.text.strip().splitlines():
            import json as _json

            try:
                obj = _json.loads(line)
                last_status = obj.get("status", last_status)
            except Exception:
                pass
        return {
            "status": "ok",
            "name": req.name,
            "ollama_status": last_status,
            "modelfile": modelfile,
        }
    except (requests.ConnectionError, requests.Timeout):
        raise HTTPException(status_code=503, detail="Cannot reach Ollama")
    except requests.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Ollama error: {e.response.text[:400]}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete")
async def delete_custom_model(req: DeleteModelRequest):
    """Delete a model from Ollama by name."""
    try:
        resp = requests.delete(
            f"{_ollama_url()}/api/delete",
            json={"name": req.name},
            timeout=30,
        )
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Model not found: {req.name}")
        resp.raise_for_status()
        return {"status": "deleted", "name": req.name}
    except HTTPException:
        raise
    except (requests.ConnectionError, requests.Timeout):
        raise HTTPException(status_code=503, detail="Cannot reach Ollama")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
