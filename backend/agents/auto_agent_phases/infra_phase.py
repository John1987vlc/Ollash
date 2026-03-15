"""Phase 6: InfraPhase — template-driven infrastructure file generation.

Creates: .gitignore, requirements.txt (or package.json), Dockerfile.
Uses hardcoded templates for most files. One LLM call only for dependency inference.
Skips files that already exist in ctx.generated_files.
"""

from __future__ import annotations

import re
from typing import List, Set

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext

_GITIGNORE_PYTHON = """__pycache__/
*.pyc
*.pyo
*.pyd
.env
.venv/
venv/
env/
dist/
build/
*.egg-info/
.mypy_cache/
.ruff_cache/
.pytest_cache/
*.db
.DS_Store
"""

_GITIGNORE_NODE = """node_modules/
dist/
build/
.env
.env.local
*.log
.DS_Store
coverage/
"""

_DOCKERFILE_PYTHON = """FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
"""

_DOCKERFILE_NODE = """FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
CMD ["node", "dist/index.js"]
"""

_REQUIREMENTS_SYSTEM = (
    "Output a requirements.txt file. List only third-party pip packages. "
    "No stdlib. No comments. One package per line with version pins. Output only the file content."
)

_REQUIREMENTS_USER = """Tech stack: {tech_stack}
Project type: {project_type}
Import statements found in project:
{imports_found}

Output requirements.txt (third-party packages only, one per line):"""

_PACKAGE_JSON_TEMPLATE = """{
  "name": "{project_name}",
  "version": "1.0.0",
  "description": "{description}",
  "main": "dist/index.js",
  "scripts": {
    "build": "tsc",
    "start": "node dist/index.js",
    "dev": "ts-node src/index.ts"
  },
  "dependencies": {},
  "devDependencies": {
    "typescript": "^5.0.0",
    "@types/node": "^20.0.0"
  }
}
"""

# Standard Python stdlib modules (incomplete but covers common ones)
_STDLIB = {
    "os",
    "sys",
    "re",
    "json",
    "pathlib",
    "typing",
    "abc",
    "time",
    "datetime",
    "collections",
    "itertools",
    "functools",
    "copy",
    "math",
    "random",
    "hashlib",
    "hmac",
    "base64",
    "uuid",
    "io",
    "struct",
    "logging",
    "threading",
    "asyncio",
    "concurrent",
    "subprocess",
    "shutil",
    "tempfile",
    "glob",
    "fnmatch",
    "csv",
    "configparser",
    "argparse",
    "ast",
    "inspect",
    "importlib",
    "pkgutil",
    "contextlib",
    "dataclasses",
    "enum",
    "traceback",
    "warnings",
    "weakref",
    "gc",
    "platform",
    "socket",
    "ssl",
    "http",
    "urllib",
    "email",
    "html",
    "xml",
    "unittest",
    "doctest",
    "pdb",
    "profile",
    "timeit",
    "dis",
    "__future__",
    "builtins",
}


class InfraPhase(BasePhase):
    phase_id = "6"
    phase_label = "Infra"

    def run(self, ctx: PhaseContext) -> None:
        has_python = "python" in ctx.tech_stack
        has_node = any(t in ctx.tech_stack for t in ("javascript", "typescript", "react", "vue"))

        # .gitignore — always
        if ".gitignore" not in ctx.generated_files:
            gitignore = _GITIGNORE_NODE if has_node else _GITIGNORE_PYTHON
            self._write_file(ctx, ".gitignore", gitignore)

        # requirements.txt (Python)
        if has_python and "requirements.txt" not in ctx.generated_files:
            self._generate_requirements(ctx)

        # package.json (Node/TS)
        if has_node and "package.json" not in ctx.generated_files:
            self._generate_package_json(ctx)

        # Dockerfile
        if "Dockerfile" not in ctx.generated_files:
            dockerfile = _DOCKERFILE_NODE if has_node else _DOCKERFILE_PYTHON
            self._write_file(ctx, "Dockerfile", dockerfile)

        ctx.logger.info("[Infra] Infrastructure files written")

    def _generate_requirements(self, ctx: PhaseContext) -> None:
        """Scan Python imports and ask LLM to identify third-party packages."""
        imports_found = self._scan_python_imports(ctx)

        user = _REQUIREMENTS_USER.format(
            tech_stack=", ".join(ctx.tech_stack),
            project_type=ctx.project_type,
            imports_found="\n".join(imports_found[:40]),
        )

        content = self._llm_call(ctx, _REQUIREMENTS_SYSTEM, user, role="coder")
        if content:
            # Clean up: remove markdown fences if present
            content = re.sub(r"```[a-z]*\n?", "", content).strip()
            self._write_file(ctx, "requirements.txt", content + "\n")

    def _generate_package_json(self, ctx: PhaseContext) -> None:
        """Write a minimal package.json from template."""
        content = _PACKAGE_JSON_TEMPLATE.format(
            project_name=ctx.project_name.lower().replace(" ", "-"),
            description=ctx.project_description[:100],
        )
        self._write_file(ctx, "package.json", content)

    def _scan_python_imports(self, ctx: PhaseContext) -> List[str]:
        """Extract third-party import names from all .py files."""
        third_party: Set[str] = set()
        for path, content in ctx.generated_files.items():
            if not path.endswith(".py"):
                continue
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("import "):
                    mod = line.split()[1].split(".")[0]
                    if mod not in _STDLIB:
                        third_party.add(f"import {mod}")
                elif line.startswith("from "):
                    parts = line.split()
                    if len(parts) >= 2:
                        mod = parts[1].split(".")[0]
                        if mod not in _STDLIB and not mod.startswith("."):
                            third_party.add(f"from {mod}")
        return sorted(third_party)
