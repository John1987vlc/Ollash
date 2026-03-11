"""
common_router - migrated from common_bp.py.
Handles shared routes like index and health status.
"""

import os
import requests
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from backend.api.app import get_templates

router = APIRouter(tags=["common"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    templates = get_templates()
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    templates = get_templates()
    return templates.TemplateResponse("pages/chat.html", {"request": request})


@router.get("/api/status")
async def status(request: Request):
    """Health check — verifies Ollama connectivity."""
    try:
        # Prioritize central OLLAMA_URL and fall back to OLLASH_OLLAMA_URL or default
        ollama_url = os.environ.get("OLLAMA_URL", os.environ.get("OLLASH_OLLAMA_URL", "http://127.0.0.1:11434"))
        # Ensure URL is clean
        ollama_url = ollama_url.rstrip("/")

        resp = requests.get(f"{ollama_url}/api/tags", timeout=5)
        resp.raise_for_status()

        models = [m["name"] for m in resp.json().get("models", [])]
        return {"status": "ok", "ollama_url": ollama_url, "models": models}
    except (requests.ConnectionError, requests.Timeout):
        return {"status": "error", "message": "Cannot connect to Ollama (Connection Refused or Timeout)"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/api/docs/tree")
async def get_docs_tree():
    """Returns the dynamic documentation tree."""
    try:
        from backend.core.containers import main_container

        doc_manager = main_container.core.documentation_manager()
        tree = doc_manager.get_documentation_tree()
        return tree
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/docs/content/{rel_path:path}")
async def get_doc_content(rel_path: str):
    """Returns the content of a specific documentation file."""
    try:
        from backend.core.containers import main_container

        doc_manager = main_container.core.documentation_manager()
        content = doc_manager.get_documentation_content(rel_path)
        if content is None:
            raise HTTPException(status_code=404, detail="File not found or access denied")
        return {"content": content, "path": rel_path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/Ollash.jpg")
async def get_logo(request: Request):
    """Serve the main logo from the root."""
    root = request.app.state.ollash_root_dir.parent
    logo_path = root / "Ollash.jpg"
    if logo_path.exists():
        return FileResponse(logo_path)
    raise HTTPException(status_code=404, detail="Logo not found")
