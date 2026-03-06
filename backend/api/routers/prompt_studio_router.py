"""
prompt_studio_router - migrated from prompt_studio_bp.py.
Handles prompt roles, loading, saving, and history.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter(prefix="/prompts", tags=["prompt-studio"])


class SavePromptRequest(BaseModel):
    role: str
    prompt: str


class ValidatePromptRequest(BaseModel):
    prompt: str


def get_prompt_repo(request: Request):
    """Return prompt repository from app state or initialize it."""
    if not hasattr(request.app.state, "prompt_repository"):
        from backend.core.containers import main_container
        try:
            request.app.state.prompt_repository = main_container.core.prompt_repository()
        except Exception:
            return None
    return request.app.state.prompt_repository


def get_prompts_dir(request: Request) -> Path:
    return request.app.state.ollash_root_dir / "prompts"


@router.get("/api/roles")
async def list_roles(request: Request):
    """List all available roles (from filesystem and DB)."""
    roles = set()
    prompts_dir = get_prompts_dir(request)

    # 1. From filesystem
    if prompts_dir.exists():
        for f in prompts_dir.glob("**/*.yaml"):
            roles.add(f.stem)
        for f in prompts_dir.glob("**/*.json"):
            roles.add(f.stem)

    return {"roles": sorted(list(roles))}


@router.get("/api/load/{role}")
async def load_role_prompt(role: str, request: Request):
    """Load the active prompt for a role (DB preferred, then filesystem)."""
    repo = get_prompt_repo(request)
    prompts_dir = get_prompts_dir(request)

    # 1. Try DB
    if repo:
        active = repo.get_active_prompt(role)
        if active:
            return {"role": role, "prompt": active, "source": "database"}

    # 2. Try Filesystem fallback
    if prompts_dir.exists():
        for ext in [".yaml", ".json"]:
            found = list(prompts_dir.glob(f"**/{role}{ext}"))
            if found:
                try:
                    with open(found[0], "r", encoding="utf-8") as f:
                        if ext == ".yaml":
                            raw_text = f.read()
                            return {"role": role, "prompt": raw_text, "source": "filesystem"}
                        else:
                            content = json.load(f)
                            text = content.get("prompt") or content.get("system_prompt") or json.dumps(content, indent=2)
                            return {"role": role, "prompt": text, "source": "filesystem"}
                except Exception as e:
                    raise HTTPException(status_code=500, detail=str(e))

    raise HTTPException(status_code=404, detail="Prompt not found")


@router.post("/api/migrate")
async def migrate_to_db(request: Request):
    """Migrate all filesystem prompts to the database."""
    repo = get_prompt_repo(request)
    prompts_dir = get_prompts_dir(request)

    if not repo or not prompts_dir.exists():
        raise HTTPException(status_code=500, detail="Repository or prompts dir not available")

    count = 0
    try:
        for ext in [".yaml", ".json"]:
            for f in prompts_dir.glob(f"**/*{ext}"):
                role = f.stem
                with open(f, "r", encoding="utf-8") as fh:
                    if ext == ".yaml":
                        content = fh.read()
                    else:
                        data = json.load(fh)
                        content = data.get("prompt") or data.get("system_prompt") or json.dumps(data, indent=2)

                    repo.save_prompt(role, content, is_active=True)
                    count += 1

        return {"status": "success", "migrated": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/save")
async def save_prompt(payload: SavePromptRequest, request: Request):
    """Save a modified prompt to the database."""
    repo = get_prompt_repo(request)
    if not repo:
        raise HTTPException(status_code=503, detail="Repository not available")

    try:
        prompt_id = repo.save_prompt(payload.role, payload.prompt, is_active=True)
        return {"success": True, "id": prompt_id, "message": f"Prompt for '{payload.role}' saved and activated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/history/{role}")
async def get_history(role: str, request: Request):
    """Get version history for a role from the DB."""
    repo = get_prompt_repo(request)
    if repo:
        history = repo.get_history(role)
        return {"history": history}
    return {"history": []}


@router.post("/api/validate")
async def validate_prompt(payload: ValidatePromptRequest):
    """Validation logic."""
    prompt_text = payload.prompt
    warnings = []
    if len(prompt_text) < 50:
        warnings.append({"severity": "warning", "message": "Prompt is too short. Context may be lost."})
    if "ignore previous instructions" in prompt_text.lower():
        warnings.append({"severity": "critical", "message": "Potential Prompt Injection detected."})
    if "{{" not in prompt_text and "{" not in prompt_text:
        warnings.append({"severity": "info", "message": "No dynamic variables found."})

    return {"valid": len(warnings) == 0, "warnings": warnings}


@router.get("/")
async def prompt_studio_index():
    return {"status": "ok", "router": "prompt-studio"}
