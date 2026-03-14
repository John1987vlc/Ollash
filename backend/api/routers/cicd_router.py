"""CICD router — generate CI/CD configs and check pipeline status."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/cicd", tags=["cicd"])

_CICD_FILES = [
    ".github/workflows",
    ".gitlab-ci.yml",
    "Jenkinsfile",
    "azure-pipelines.yml",
    ".circleci/config.yml",
    "Dockerfile",
    "docker-compose.yml",
    ".travis.yml",
]


class CICDGenerateRequest(BaseModel):
    project_path: str
    project_description: str = ""
    stack: str = "python"


@router.get("/")
async def cicd_index():
    return {"status": "ok", "endpoints": ["/generate", "/status"]}


@router.get("/status")
async def cicd_status(project_path: str = "."):
    """Detect existing CI/CD configuration in a project."""
    root = Path(project_path).resolve()
    found: list[dict] = []
    for pattern in _CICD_FILES:
        p = root / pattern
        if p.exists():
            if p.is_dir():
                files = list(p.glob("*.yml")) + list(p.glob("*.yaml"))
                for f in files:
                    found.append({"path": str(f.relative_to(root)), "type": "github_actions"})
            else:
                found.append(
                    {
                        "path": str(p.relative_to(root)),
                        "type": p.name.split(".")[0] if p.name.startswith(".") else p.stem,
                    }
                )
    return {
        "project_path": str(root),
        "has_cicd": len(found) > 0,
        "configs": found,
    }


@router.post("/generate")
async def generate_cicd(req: CICDGenerateRequest):
    """Generate a CI/CD configuration for the given project using the LLM."""
    try:
        from backend.core.containers import main_container

        llm_manager = main_container.auto_agent_module.llm_client_manager()
        client = llm_manager.get_client("coder")

        project_path = Path(req.project_path).resolve()
        # Gather a brief file listing for context
        try:
            files = [
                str(f.relative_to(project_path))
                for f in project_path.rglob("*")
                if f.is_file() and not any(p in str(f) for p in [".git", "__pycache__", "node_modules"])
            ][:50]
            file_list = "\n".join(files)
        except Exception:
            file_list = "Could not list project files"

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a DevOps engineer. Generate a complete, production-ready CI/CD configuration. "
                    "Output ONLY the file content with no explanations."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Generate a GitHub Actions CI/CD workflow for a {req.stack} project.\n"
                    f"Description: {req.project_description or 'No description provided'}\n\n"
                    f"Project files:\n{file_list}\n\n"
                    "Generate a complete `.github/workflows/ci.yml` file."
                ),
            },
        ]

        result, usage = await asyncio.wait_for(client.achat(messages), timeout=120)
        content = result.get("content", "")

        return {
            "status": "ok",
            "content": content,
            "suggested_path": ".github/workflows/ci.yml",
            "tokens": usage,
        }
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Generation timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
