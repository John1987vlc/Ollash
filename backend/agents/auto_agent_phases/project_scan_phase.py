"""Phase 1: ProjectScanPhase — zero-LLM project analysis.

Detects project type and tech stack from the description using keyword matching.
If the project root already contains files, ingests them into ctx.generated_files.
No LLM calls. Runs in milliseconds.
"""

from __future__ import annotations

from typing import List

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext

_SOURCE_EXTS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".html",
    ".css",
    ".sql",
}

_IGNORE_DIRS = {".git", ".ollash", ".venv", "__pycache__", "node_modules", ".cache"}

_TECH_KEYWORDS: dict = {
    "python": ["python", "flask", "fastapi", "django", "uvicorn", "pydantic"],
    "fastapi": ["fastapi"],
    "flask": ["flask"],
    "django": ["django"],
    "javascript": ["javascript", "node", "express", "react", "vue", "angular", " js ", " js,", " js."],
    "typescript": ["typescript", ".ts", "tsx"],
    "react": ["react", "jsx", "tsx"],
    "vue": ["vue"],
    "html": ["html", " htm "],
    "css": ["css", "stylesheet", "estilo", "estilos"],
    "svg": ["svg"],
    "sqlite": ["sqlite"],
    "postgresql": ["postgresql", "postgres", "psycopg"],
    "docker": ["docker", "container", "dockerfile"],
    "cli": ["cli", "command line", "terminal", "argparse", "click", "typer"],
    "api": ["api", "rest", "graphql", "endpoint", "openapi"],
    "game": ["game", "pygame", "unity", "phaser", "canvas", "juego", "carta", "cartas"],
    "data": ["pandas", "numpy", "sklearn", "machine learning", "data science", "jupyter"],
}

_TYPE_HINTS: dict = {
    "frontend_web": [
        "html",
        "css",
        " js ",
        "javascript",
        "frontend",
        "web app",
        "website",
        "browser",
        "svg",
        "juego de cartas",
        "card game",
    ],
    "api": ["api", "rest", "fastapi", "flask", "django", "endpoint", "graphql"],
    "cli": ["cli", "command line", "terminal", "script"],
    "library": ["library", "package", "module", "sdk"],
    "game": ["game", "pygame", "canvas", "phaser", "juego", "pygame"],
    "data": ["data", "pandas", "ml", "machine learning", "jupyter", "analysis"],
}


class ProjectScanPhase(BasePhase):
    phase_id = "1"
    phase_label = "Project Scan"

    def run(self, ctx: PhaseContext) -> None:
        desc_lower = ctx.project_description.lower()

        # Detect project type from description
        ctx.project_type = self._detect_type(desc_lower)

        # Detect tech stack from description
        ctx.tech_stack = self._detect_stack(desc_lower)

        # Use ProjectTypeDetector if available (zero-LLM, keyword-based)
        try:
            from backend.utils.domains.auto_generation.utilities.project_type_detector import (
                ProjectTypeDetector,
            )

            type_info = ProjectTypeDetector.detect(ctx.project_description, readme_content="")
            if type_info and type_info.project_type and type_info.project_type != "unknown":
                ctx.project_type = type_info.project_type
        except Exception:
            pass  # Fallback to our own detection above

        # Ingest existing project files if root exists and has content
        if ctx.project_root.exists():
            self._ingest_existing(ctx)

        ctx.logger.info(
            f"[Scan] type={ctx.project_type}, stack={ctx.tech_stack}, existing_files={len(ctx.generated_files)}"
        )

    def _detect_type(self, desc_lower: str) -> str:
        scores: dict = {}
        for ptype, hints in _TYPE_HINTS.items():
            scores[ptype] = sum(1 for h in hints if h in desc_lower)
        best = max(scores, key=lambda k: scores[k])
        return best if scores[best] > 0 else "unknown"

    def _detect_stack(self, desc_lower: str) -> List[str]:
        stack = []
        for tech, patterns in _TECH_KEYWORDS.items():
            if any(p in desc_lower for p in patterns):
                stack.append(tech)
        if not stack:
            # Infer default from detected type
            ptype = self._detect_type(desc_lower)
            if ptype == "frontend_web":
                return ["html", "javascript", "css"]
            return ["python"]
        return stack

    def _ingest_existing(self, ctx: PhaseContext) -> None:
        """Load existing source files into ctx.generated_files (cap at 50)."""
        count = 0
        for path in ctx.project_root.rglob("*"):
            if count >= 50:
                break
            if not path.is_file():
                continue
            # Skip ignored directories
            if any(part in _IGNORE_DIRS for part in path.parts):
                continue
            if path.suffix.lower() not in _SOURCE_EXTS:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                rel = str(path.relative_to(ctx.project_root))
                ctx.generated_files[rel] = content
                count += 1
            except Exception:
                pass
