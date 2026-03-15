"""Phase 3: ScaffoldPhase — zero-LLM directory and stub file creation.

Creates all directories and writes minimal stub files for each entry in ctx.blueprint.
Files already in ctx.generated_files (ingested from disk in Phase 1) are skipped.
No LLM calls. Runs in milliseconds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import FilePlan, PhaseContext

_STUBS: Dict[str, str] = {
    ".py": "# {purpose}\n",
    ".ts": "// {purpose}\n",
    ".tsx": "// {purpose}\n",
    ".js": "// {purpose}\n",
    ".jsx": "// {purpose}\n",
    ".go": "// {purpose}\npackage main\n",
    ".rs": "// {purpose}\n",
    ".java": "// {purpose}\n",
    ".md": "# {name}\n\n{purpose}\n",
    ".json": "{{\n}}\n",
    ".yaml": "# {purpose}\n",
    ".yml": "# {purpose}\n",
    ".toml": "# {purpose}\n",
    ".html": "<!DOCTYPE html>\n<html>\n<head><title>{name}</title></head>\n<body>\n<!-- {purpose} -->\n</body>\n</html>\n",
    ".css": "/* {purpose} */\n",
    ".scss": "/* {purpose} */\n",
    ".sql": "-- {purpose}\n",
    ".sh": "#!/bin/bash\n# {purpose}\n",
    ".env": "# Environment variables\n",
    ".gitignore": "__pycache__/\n*.pyc\n.env\n.venv/\ndist/\nbuild/\nnode_modules/\n.DS_Store\n",
    ".txt": "",
    ".dockerfile": "FROM python:3.12-slim\n",
}


class ScaffoldPhase(BasePhase):
    phase_id = "3"
    phase_label = "Scaffold"

    def run(self, ctx: PhaseContext) -> None:
        ctx.project_root.mkdir(parents=True, exist_ok=True)
        created = 0

        for plan in ctx.blueprint:
            if plan.path in ctx.generated_files:
                # Already ingested from existing project — do not overwrite
                continue

            abs_path = ctx.project_root / plan.path
            abs_path.parent.mkdir(parents=True, exist_ok=True)

            stub = self._make_stub(plan)
            abs_path.write_text(stub, encoding="utf-8")
            ctx.generated_files[plan.path] = stub
            created += 1

        ctx.logger.info(f"[Scaffold] Created {created} stub files")

    def _make_stub(self, plan: FilePlan) -> str:
        ext = Path(plan.path).suffix.lower()

        # Special case: Dockerfile has no extension
        if Path(plan.path).name.lower() == "dockerfile":
            return _STUBS[".dockerfile"]

        template = _STUBS.get(ext, "# {purpose}\n")
        return template.format(
            purpose=plan.purpose,
            name=Path(plan.path).stem,
        )
