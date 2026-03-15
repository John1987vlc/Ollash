"""Phase 6: InfraPhase — template-driven infrastructure file generation.

Creates: .gitignore, requirements.txt (or package.json), Dockerfile.
Uses hardcoded templates for most files. One LLM call only for dependency inference.
Skips files that already exist in ctx.generated_files.

Improvements:
  #12 — Smart entrypoint detection: finds the true entry file for Dockerfile CMD
  #16 — Plugin architecture: each infra concern is an InfraPlugin with can_handle/apply
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import List, Set

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

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
CMD ["python", "{entrypoint}"]
"""

_DOCKERFILE_NODE = """FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
CMD ["node", "{entrypoint}"]
"""

_DOCKERFILE_FRONTEND = """FROM nginx:alpine
COPY . /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
"""

_PACKAGE_JSON_FRONTEND = """{{
  "name": "{project_name}",
  "version": "1.0.0",
  "description": "{description}",
  "scripts": {{
    "start": "npx serve . -l 8080",
    "dev": "npx live-server --port=8080"
  }},
  "dependencies": {{}},
  "devDependencies": {{
    "serve": "^14.0.0"
  }}
}}
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

_PACKAGE_JSON_TEMPLATE = """{{
  "name": "{project_name}",
  "version": "1.0.0",
  "description": "{description}",
  "main": "{entrypoint}",
  "scripts": {{
    "start": "node {entrypoint}",
    "dev": "node {entrypoint}"
  }},
  "dependencies": {{}},
  "devDependencies": {{}}
}}
"""

# Standard Python stdlib modules
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


# ---------------------------------------------------------------------------
# #16 — Plugin base class
# ---------------------------------------------------------------------------


class InfraPlugin(ABC):
    """Base class for infrastructure generation plugins.

    Each plugin handles one concern (gitignore, requirements, Dockerfile, etc.).
    Plugins are applied in order; each is responsible for checking if it should
    run and for writing its output to ctx.
    """

    @abstractmethod
    def can_handle(self, ctx: PhaseContext) -> bool:
        """Return True if this plugin should run for the given project context."""
        ...

    @abstractmethod
    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        """Apply this plugin. Writes files to ctx via phase._write_file()."""
        ...


class GitignorePlugin(InfraPlugin):
    def can_handle(self, ctx: PhaseContext) -> bool:
        return ".gitignore" not in ctx.generated_files

    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        has_node = any(t in ctx.tech_stack for t in ("javascript", "typescript", "react", "vue"))
        is_frontend = ctx.project_type in ("frontend_web", "web_app")
        gitignore = _GITIGNORE_NODE if (has_node or is_frontend) else _GITIGNORE_PYTHON
        phase._write_file(ctx, ".gitignore", gitignore)
        ctx.logger.info("[Infra/GitignorePlugin] .gitignore written")


class RequirementsPlugin(InfraPlugin):
    def can_handle(self, ctx: PhaseContext) -> bool:
        return "python" in ctx.tech_stack and "requirements.txt" not in ctx.generated_files

    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        imports_found = phase._scan_python_imports(ctx)
        user = _REQUIREMENTS_USER.format(
            tech_stack=", ".join(ctx.tech_stack),
            project_type=ctx.project_type,
            imports_found="\n".join(imports_found[:40]),
        )
        content = phase._llm_call(ctx, _REQUIREMENTS_SYSTEM, user, role="coder")
        if content:
            content = re.sub(r"```[a-z]*\n?", "", content).strip()
            phase._write_file(ctx, "requirements.txt", content + "\n")
            ctx.logger.info("[Infra/RequirementsPlugin] requirements.txt written")


class PackageJsonPlugin(InfraPlugin):
    def can_handle(self, ctx: PhaseContext) -> bool:
        has_node = any(t in ctx.tech_stack for t in ("javascript", "typescript", "react", "vue"))
        is_frontend = ctx.project_type in ("frontend_web", "web_app")
        return (has_node or is_frontend) and "package.json" not in ctx.generated_files

    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        is_frontend = ctx.project_type in ("frontend_web", "web_app")
        project_name = ctx.project_name.lower().replace(" ", "-")
        description = ctx.project_description[:100]

        if is_frontend:
            content = _PACKAGE_JSON_FRONTEND.format(
                project_name=project_name,
                description=description,
            )
        else:
            # #12 — detect JS entrypoint
            entrypoint = phase._find_js_entrypoint(ctx)
            content = _PACKAGE_JSON_TEMPLATE.format(
                project_name=project_name,
                description=description,
                entrypoint=entrypoint,
            )
        phase._write_file(ctx, "package.json", content)
        ctx.logger.info("[Infra/PackageJsonPlugin] package.json written")


class DockerfilePlugin(InfraPlugin):
    def can_handle(self, ctx: PhaseContext) -> bool:
        return "Dockerfile" not in ctx.generated_files

    def apply(self, phase: "InfraPhase", ctx: PhaseContext) -> None:
        has_node = any(t in ctx.tech_stack for t in ("javascript", "typescript", "react", "vue"))
        is_frontend = ctx.project_type in ("frontend_web", "web_app")

        if is_frontend:
            content = _DOCKERFILE_FRONTEND
        elif has_node:
            entrypoint = phase._find_js_entrypoint(ctx)
            content = _DOCKERFILE_NODE.format(entrypoint=entrypoint)
        else:
            entrypoint = phase._find_python_entrypoint(ctx)  # #12
            content = _DOCKERFILE_PYTHON.format(entrypoint=entrypoint)

        phase._write_file(ctx, "Dockerfile", content)
        ctx.logger.info("[Infra/DockerfilePlugin] Dockerfile written (entrypoint inferred)")


# ---------------------------------------------------------------------------
# InfraPhase
# ---------------------------------------------------------------------------


class InfraPhase(BasePhase):
    phase_id = "6"
    phase_label = "Infra"

    # #16 — Ordered list of plugins
    PLUGINS: List[InfraPlugin] = [
        GitignorePlugin(),
        RequirementsPlugin(),
        PackageJsonPlugin(),
        DockerfilePlugin(),
    ]

    def run(self, ctx: PhaseContext) -> None:
        for plugin in self.PLUGINS:
            if plugin.can_handle(ctx):
                try:
                    plugin.apply(self, ctx)
                except Exception as e:
                    ctx.logger.warning(f"[Infra] Plugin {plugin.__class__.__name__} failed: {e}")
        ctx.logger.info("[Infra] Infrastructure files complete")

    # ----------------------------------------------------------------
    # #12 — Smart entrypoint detection
    # ----------------------------------------------------------------

    @staticmethod
    def _find_python_entrypoint(ctx: PhaseContext) -> str:
        """Find the Python entry file: lowest-priority file with no importers.

        Preference order:
        1. File named main.py, app.py, cli.py, run.py, server.py
        2. Leaf node in the import graph (no other file imports it)
        3. Fallback to 'main.py'
        """
        preferred = ("main.py", "app.py", "cli.py", "run.py", "server.py")
        for name in preferred:
            if name in ctx.generated_files:
                return name

        # Find blueprint leaf nodes (files that no one imports) among Python files
        all_imports: Set[str] = set()
        for fp in ctx.blueprint:
            all_imports.update(fp.imports)

        py_files = [fp.path for fp in ctx.blueprint if fp.path.endswith(".py") and fp.path not in all_imports]
        if py_files:
            # Pick the one with highest priority number (generated last = typically entry)
            py_files.sort(key=lambda p: next((fp.priority for fp in ctx.blueprint if fp.path == p), 0), reverse=True)
            return py_files[0]

        return "main.py"

    @staticmethod
    def _find_js_entrypoint(ctx: PhaseContext) -> str:
        """Find the JS/TS entry file using the same leaf-node heuristic."""
        preferred = ("index.js", "main.js", "app.js", "server.js", "index.ts", "main.ts")
        for name in preferred:
            if name in ctx.generated_files:
                return name

        all_imports: Set[str] = set()
        for fp in ctx.blueprint:
            all_imports.update(fp.imports)

        js_files = [fp.path for fp in ctx.blueprint if fp.path.endswith((".js", ".ts")) and fp.path not in all_imports]
        if js_files:
            js_files.sort(key=lambda p: next((fp.priority for fp in ctx.blueprint if fp.path == p), 0), reverse=True)
            return js_files[0]

        return "index.js"

    # ----------------------------------------------------------------
    # Utilities (used by plugins)
    # ----------------------------------------------------------------

    @staticmethod
    def _scan_python_imports(ctx: PhaseContext) -> List[str]:
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
