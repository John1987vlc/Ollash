"""ProjectCreationTools — stateful toolset for AutoAgentWithTools.

Each instance is bound to a single project_root for one run() invocation.
Tools are NOT registered in the global ToolRegistry — they are called directly
by AutoAgentWithTools._dispatch_tool_call() to avoid the ConfirmationManager gate.
Tool schemas (TOOL_DEFINITIONS) are passed to OllamaClient as the `tools` argument.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class ProjectCreationTools:
    """Sandboxed project-creation tools for the tool-calling agent.

    All write operations are restricted to project_root via _safe_path().
    No LLM calls are made here — the tools are pure Python side-effects.
    """

    TOOL_DEFINITIONS: List[Dict[str, Any]] = [
        {
            "type": "function",
            "function": {
                "name": "plan_project",
                "description": (
                    "Record the project blueprint. Call this FIRST before writing any files. "
                    "Accepts a JSON string with the full project plan."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "blueprint_json": {
                            "type": "string",
                            "description": (
                                "JSON string with keys: project_type (str), tech_stack (list[str]), "
                                "files (list of {path: str, purpose: str}). "
                                'Example: {"project_type":"api","tech_stack":["python","fastapi"],'
                                '"files":[{"path":"main.py","purpose":"FastAPI entry point"}]}'
                            ),
                        }
                    },
                    "required": ["blueprint_json"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_project_file",
                "description": (
                    "Generate and write a file into the project directory. "
                    "Path must be relative (e.g. 'src/main.py'). "
                    "Provide a detailed spec of what the file must contain — "
                    "a dedicated code-generation model will produce the actual code."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "relative_path": {
                            "type": "string",
                            "description": "Relative path within the project (e.g. 'src/main.py').",
                        },
                        "spec": {
                            "type": "string",
                            "description": (
                                "2-4 sentence description of the file's complete requirements: "
                                "what it exports, what functions/classes it contains, "
                                "what libraries it uses, and how it fits in the project. "
                                "Be specific — this description drives code generation."
                            ),
                        },
                    },
                    "required": ["relative_path", "spec"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_project_file",
                "description": "Read the content of an existing file in the project.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "relative_path": {
                            "type": "string",
                            "description": "Relative path of the file to read.",
                        }
                    },
                    "required": ["relative_path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_project_files",
                "description": "List all files currently in the project directory with their sizes.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_linter",
                "description": (
                    "Run a syntax/style linter on a project file. "
                    "Python → ruff check; TypeScript/JavaScript → node --check; "
                    "Other → basic parse check. Returns issues found."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "relative_path": {
                            "type": "string",
                            "description": "Relative path of the file to lint.",
                        }
                    },
                    "required": ["relative_path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_project_tests",
                "description": (
                    "Run the project's test suite. "
                    "Auto-detects pytest (Python) or jest/vitest (JS/TS). "
                    "Returns pass/fail status and output."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_infrastructure",
                "description": (
                    "Auto-generate infrastructure files: .gitignore, requirements.txt (Python) "
                    "or package.json (JS/TS), and a minimal Dockerfile. "
                    "Detects language from files already written."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "finish_project",
                "description": (
                    "Finalize the project: write README.md and OLLASH.md with run metadata. "
                    "This MUST be the last tool you call. Signals that generation is complete."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Short summary of what was built (1-3 sentences).",
                        }
                    },
                    "required": ["summary"],
                },
            },
        },
    ]

    # Skip dirs when listing files
    _SKIP_DIRS = {"__pycache__", "node_modules", ".venv", "venv", ".git", ".ollash"}

    def __init__(
        self,
        project_root: Path,
        event_publisher: Any,
        logger: Any,
        on_blueprint_ready: Optional[Callable[[Dict[str, Any]], bool]] = None,
        orchestrator_model: str = "tool_agent",
        code_model: str = "code_generator",
    ) -> None:
        self.project_root = project_root
        self._event_publisher = event_publisher
        self._logger = logger
        self._on_blueprint_ready = on_blueprint_ready
        self._orchestrator_model = orchestrator_model
        self._code_model = code_model

        self._blueprint: Optional[Dict[str, Any]] = None
        self._files_written: Dict[str, int] = {}  # relative_path → byte count
        self._start_time: float = time.time()
        self.finished: bool = False
        self._aborted: bool = False
        self._finish_summary: str = ""
        self._total_tokens: int = 0

    # ------------------------------------------------------------------
    # Security helper
    # ------------------------------------------------------------------

    def _safe_path(self, relative: str) -> Path:
        """Resolve relative path and verify it stays within project_root."""
        resolved = (self.project_root / relative).resolve()
        if not resolved.is_relative_to(self.project_root.resolve()):
            raise ValueError(f"Path traversal attempt: '{relative}'")
        return resolved

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def plan_project(self, blueprint_json: str) -> Dict[str, Any]:
        """Record the project blueprint."""
        try:
            blueprint = json.loads(blueprint_json)
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"Invalid JSON in blueprint_json: {e}"}

        if not isinstance(blueprint, dict):
            return {"ok": False, "error": "blueprint_json must be a JSON object."}

        self._blueprint = blueprint
        files = blueprint.get("files", [])

        # Call on_blueprint_ready callback if set
        if self._on_blueprint_ready is not None:
            try:
                result = self._on_blueprint_ready(blueprint)
                if result is False:
                    self._aborted = True
                    return {"ok": False, "error": "Pipeline aborted by on_blueprint_ready callback."}
            except Exception as e:
                self._logger.warning(f"[ProjectCreationTools] on_blueprint_ready error: {e}")

        # Create project root
        self.project_root.mkdir(parents=True, exist_ok=True)

        await self._publish(
            "phase_start",
            {
                "phase": f"Planning: {len(files)} files",
                "blueprint": blueprint,
            },
        )

        return {
            "ok": True,
            "files_planned": len(files),
            "project_type": blueprint.get("project_type", "unknown"),
            "tech_stack": blueprint.get("tech_stack", []),
        }

    async def write_project_file(self, relative_path: str, content: str) -> Dict[str, Any]:
        """Write a file to the project directory."""
        try:
            target = self._safe_path(relative_path)
        except ValueError as e:
            return {"ok": False, "error": str(e)}

        target.parent.mkdir(parents=True, exist_ok=True)

        try:
            await asyncio.to_thread(target.write_text, content, encoding="utf-8")
        except OSError as e:
            return {"ok": False, "error": f"Write failed: {e}"}

        byte_count = len(content.encode("utf-8"))
        self._files_written[relative_path] = byte_count

        await self._publish("file_generated", {"path": relative_path, "bytes": byte_count})

        return {"ok": True, "path": relative_path, "bytes": byte_count}

    async def read_project_file(self, relative_path: str) -> Dict[str, Any]:
        """Read a file from the project directory."""
        try:
            target = self._safe_path(relative_path)
        except ValueError as e:
            return {"ok": False, "error": str(e)}

        if not target.is_file():
            return {"ok": False, "error": f"File not found: {relative_path}"}

        try:
            content = await asyncio.to_thread(target.read_text, encoding="utf-8")
            return {"ok": True, "path": relative_path, "content": content}
        except OSError as e:
            return {"ok": False, "error": str(e)}

    async def list_project_files(self) -> Dict[str, Any]:
        """List all files in the project directory."""
        if not self.project_root.is_dir():
            return {"ok": True, "files": []}

        def _walk() -> List[Dict[str, Any]]:
            result = []
            for p in sorted(self.project_root.rglob("*")):
                if any(part in self._SKIP_DIRS for part in p.parts):
                    continue
                if p.is_file():
                    rel = str(p.relative_to(self.project_root))
                    result.append({"path": rel, "bytes": p.stat().st_size})
            return result

        files = await asyncio.to_thread(_walk)
        return {"ok": True, "files": files, "total": len(files)}

    async def run_linter(self, relative_path: str) -> Dict[str, Any]:
        """Run linter on a project file."""
        try:
            target = self._safe_path(relative_path)
        except ValueError as e:
            return {"ok": False, "error": str(e)}

        if not target.is_file():
            return {"ok": False, "error": f"File not found: {relative_path}"}

        ext = target.suffix.lower()

        def _run_lint() -> Dict[str, Any]:
            if ext == ".py":
                return _lint_python(target)
            elif ext in (".ts", ".tsx"):
                return _lint_ts(target, self.project_root)
            elif ext in (".js", ".mjs", ".cjs"):
                return _lint_js(target)
            else:
                return {"ok": True, "issues": [], "error_count": 0, "note": f"No linter for {ext}"}

        result = await asyncio.to_thread(_run_lint)
        await self._publish("log", {"message": f"Linter ({relative_path}): {result.get('error_count', 0)} issues"})
        return result

    async def run_project_tests(self) -> Dict[str, Any]:
        """Run the project's test suite."""
        if not self.project_root.is_dir():
            return {"ok": False, "error": "Project directory does not exist."}

        def _detect_and_run() -> Dict[str, Any]:
            cwd = str(self.project_root)
            # Python: pytest
            if list(self.project_root.rglob("test_*.py")) or (self.project_root / "tests").is_dir():
                try:
                    r = subprocess.run(
                        ["python", "-m", "pytest", "-x", "-q", "--tb=short"],
                        cwd=cwd,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    passed = r.returncode == 0
                    output = (r.stdout + r.stderr)[:3000]
                    return {"ok": True, "runner": "pytest", "passed": passed, "output": output}
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    return {"ok": False, "error": str(e)}

            # JS/TS: npm test
            pkg_json = self.project_root / "package.json"
            if pkg_json.is_file():
                try:
                    r = subprocess.run(
                        ["npm", "test", "--", "--passWithNoTests"],
                        cwd=cwd,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    passed = r.returncode == 0
                    output = (r.stdout + r.stderr)[:3000]
                    return {"ok": True, "runner": "npm test", "passed": passed, "output": output}
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    return {"ok": False, "error": str(e)}

            return {"ok": True, "runner": "none", "passed": True, "output": "No test suite detected."}

        result = await asyncio.to_thread(_detect_and_run)
        await self._publish("phase_complete", {"phase": "Tests", "passed": result.get("passed", False)})
        return result

    async def generate_infrastructure(self) -> Dict[str, Any]:
        """Generate .gitignore, requirements.txt/package.json, and Dockerfile."""
        created: List[str] = []

        # Detect dominant language
        py_count = sum(1 for p in self._files_written if p.endswith(".py"))
        ts_count = sum(1 for p in self._files_written if p.endswith((".ts", ".tsx")))
        js_count = sum(1 for p in self._files_written if p.endswith((".js", ".mjs")))
        is_python = py_count >= ts_count and py_count >= js_count
        is_node = not is_python and (ts_count + js_count) > 0

        self.project_root.mkdir(parents=True, exist_ok=True)

        # .gitignore
        gitignore_path = self.project_root / ".gitignore"
        if not gitignore_path.exists():
            content = _GITIGNORE_PYTHON if is_python else _GITIGNORE_NODE if is_node else _GITIGNORE_GENERIC
            gitignore_path.write_text(content, encoding="utf-8")
            created.append(".gitignore")

        # requirements.txt (Python)
        if is_python:
            req_path = self.project_root / "requirements.txt"
            if not req_path.exists():
                imports = _extract_third_party_imports(self.project_root)
                content = "\n".join(sorted(imports)) + "\n" if imports else "# Add dependencies here\n"
                req_path.write_text(content, encoding="utf-8")
                created.append("requirements.txt")

        # package.json stub (Node)
        if is_node:
            pkg_path = self.project_root / "package.json"
            if not pkg_path.exists():
                project_name = self.project_root.name.lower().replace(" ", "-")
                pkg = {
                    "name": project_name,
                    "version": "1.0.0",
                    "description": "",
                    "main": "index.js",
                    "scripts": {"start": "node index.js", "test": "echo 'No tests'"},
                    "dependencies": {},
                    "devDependencies": {},
                }
                pkg_path.write_text(json.dumps(pkg, indent=2), encoding="utf-8")
                created.append("package.json")

        # Dockerfile
        dockerfile_path = self.project_root / "Dockerfile"
        if not dockerfile_path.exists():
            content = _DOCKERFILE_PYTHON if is_python else _DOCKERFILE_NODE if is_node else _DOCKERFILE_GENERIC
            dockerfile_path.write_text(content, encoding="utf-8")
            created.append("Dockerfile")

        await self._publish("phase_complete", {"phase": "Infrastructure", "files_created": created})
        return {"ok": True, "files_created": created}

    async def finish_project(self, summary: str) -> Dict[str, Any]:
        """Write README.md and OLLASH.md, then signal completion."""
        self.project_root.mkdir(parents=True, exist_ok=True)
        elapsed = time.time() - self._start_time
        created: List[str] = []

        # README.md
        readme_path = self.project_root / "README.md"
        if not readme_path.exists():
            description = ""
            if self._blueprint:
                description = self._blueprint.get("description", summary)
            readme_content = _build_readme(
                project_name=self.project_root.name,
                description=description or summary,
                tech_stack=self._blueprint.get("tech_stack", []) if self._blueprint else [],
                files=list(self._files_written.keys()),
            )
            readme_path.write_text(readme_content, encoding="utf-8")
            created.append("README.md")

        # OLLASH.md (generation metadata)
        ollash_path = self.project_root / "OLLASH.md"
        ollash_content = (
            f"# OLLASH Generation Report\n\n"
            f"**Project**: {self.project_root.name}\n"
            f"**Agent**: AutoAgentWithTools (hybrid tool-calling)\n"
            f"**Orchestrator**: {self._orchestrator_model}\n"
            f"**Code generator**: {self._code_model}\n"
            f"**Generated at**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**Duration**: {elapsed:.1f}s\n"
            f"**Files**: {len(self._files_written)}\n"
            f"**Total bytes**: {sum(self._files_written.values())}\n\n"
            f"## Summary\n\n{summary}\n\n"
            f"## Files Generated\n\n" + "\n".join(f"- `{p}`" for p in sorted(self._files_written)) + "\n"
        )
        ollash_path.write_text(ollash_content, encoding="utf-8")
        created.append("OLLASH.md")

        self.finished = True
        self._finish_summary = summary

        await self._publish("phase_complete", {"phase": "Finish", "files_created": created})
        self._logger.info(
            f"[ProjectCreationTools] Project '{self.project_root.name}' finished — "
            f"{len(self._files_written)} files, {elapsed:.1f}s"
        )

        return {
            "ok": True,
            "files_total": len(self._files_written),
            "duration_seconds": round(elapsed, 1),
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def state_hint(self) -> str:
        """Return a concise next-action hint for nudging the model back to tool use."""
        if self._blueprint is None:
            return "You have NOT called plan_project() yet. Call plan_project() FIRST with a JSON blueprint."

        planned = self._blueprint.get("files", [])
        written = set(self._files_written.keys())
        remaining = [f for f in planned if f.get("path", "") not in written]

        if remaining:
            next_file = remaining[0]["path"]
            return (
                f"Blueprint recorded ({len(planned)} files planned, {len(written)} written). "
                f"Next file to write: '{next_file}'. "
                f"Call write_project_file(relative_path='{next_file}', content=...) NOW."
            )

        # All planned files written — move to infra/finish
        return (
            f"All {len(written)} file(s) written. "
            "Call generate_infrastructure() then finish_project(summary=...) to complete."
        )

    async def _publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish SSE event, swallowing all errors."""
        try:
            await self._event_publisher.publish(event_type, data)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Linter helpers (pure sync, run in thread)
# ---------------------------------------------------------------------------


def _lint_python(target: Path) -> Dict[str, Any]:
    try:
        r = subprocess.run(
            ["python", "-m", "ruff", "check", "--output-format=json", str(target)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        issues = []
        try:
            issues = json.loads(r.stdout) if r.stdout.strip() else []
        except json.JSONDecodeError:
            pass
        simplified = [
            {"line": i.get("location", {}).get("row"), "code": i.get("code"), "msg": i.get("message")} for i in issues
        ]
        return {"ok": True, "issues": simplified, "error_count": len(simplified)}
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {"ok": False, "error": str(e), "issues": [], "error_count": 0}


def _lint_ts(target: Path, project_root: Path) -> Dict[str, Any]:
    tsconfig = project_root / "tsconfig.json"
    if not tsconfig.exists():
        return _lint_js(target)
    try:
        r = subprocess.run(
            ["npx", "tsc", "--noEmit", "--allowJs", str(target)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=20,
        )
        errors = [line for line in (r.stdout + r.stderr).splitlines() if "error TS" in line]
        return {"ok": True, "issues": errors, "error_count": len(errors)}
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {"ok": False, "error": str(e), "issues": [], "error_count": 0}


def _lint_js(target: Path) -> Dict[str, Any]:
    try:
        r = subprocess.run(
            ["node", "--check", str(target)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            return {"ok": True, "issues": [], "error_count": 0}
        errors = [line for line in (r.stdout + r.stderr).splitlines() if line.strip()]
        return {"ok": True, "issues": errors, "error_count": len(errors)}
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {"ok": False, "error": str(e), "issues": [], "error_count": 0}


# ---------------------------------------------------------------------------
# Import extraction helper
# ---------------------------------------------------------------------------

_STDLIB = {
    "os",
    "sys",
    "re",
    "json",
    "time",
    "datetime",
    "pathlib",
    "typing",
    "collections",
    "itertools",
    "functools",
    "math",
    "random",
    "string",
    "hashlib",
    "hmac",
    "base64",
    "io",
    "struct",
    "copy",
    "pprint",
    "threading",
    "multiprocessing",
    "asyncio",
    "concurrent",
    "queue",
    "subprocess",
    "shutil",
    "tempfile",
    "glob",
    "fnmatch",
    "stat",
    "logging",
    "warnings",
    "traceback",
    "inspect",
    "importlib",
    "unittest",
    "dataclasses",
    "enum",
    "abc",
    "contextlib",
    "urllib",
    "http",
    "email",
    "html",
    "xml",
    "csv",
    "sqlite3",
    "socket",
    "ssl",
    "select",
    "signal",
    "ctypes",
    # common test names
    "pytest",
    "__future__",
}


def _extract_third_party_imports(project_root: Path) -> List[str]:
    """Scan .py files and extract probable third-party imports."""
    imports: set[str] = set()
    import_re = re.compile(r"^(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)")
    for py_file in project_root.rglob("*.py"):
        try:
            for line in py_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                m = import_re.match(line.strip())
                if m:
                    pkg = m.group(1).split(".")[0]
                    if pkg not in _STDLIB and not pkg.startswith("_"):
                        imports.add(pkg)
        except OSError:
            continue
    # Map common import names to PyPI package names
    _rename = {"cv2": "opencv-python", "sklearn": "scikit-learn", "PIL": "Pillow", "yaml": "pyyaml"}
    return sorted({_rename.get(p, p) for p in imports})


# ---------------------------------------------------------------------------
# Infrastructure templates
# ---------------------------------------------------------------------------

_GITIGNORE_PYTHON = """\
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
venv/
env/
.env
*.log
.pytest_cache/
.ruff_cache/
.mypy_cache/
"""

_GITIGNORE_NODE = """\
node_modules/
dist/
build/
.env
*.log
.DS_Store
coverage/
"""

_GITIGNORE_GENERIC = """\
*.log
.env
dist/
build/
"""

_DOCKERFILE_PYTHON = """\
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
"""

_DOCKERFILE_NODE = """\
FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci --omit=dev
COPY . .
CMD ["node", "index.js"]
"""

_DOCKERFILE_GENERIC = """\
FROM ubuntu:22.04
WORKDIR /app
COPY . .
CMD ["/bin/bash"]
"""


def _build_readme(
    project_name: str,
    description: str,
    tech_stack: List[str],
    files: List[str],
) -> str:
    stack_line = ", ".join(tech_stack) if tech_stack else "General"
    file_list = "\n".join(f"- `{f}`" for f in sorted(files)) if files else "_(no files)_"
    return (
        f"# {project_name}\n\n"
        f"{description}\n\n"
        f"## Stack\n\n{stack_line}\n\n"
        f"## Project Files\n\n{file_list}\n\n"
        f"---\n_Generated by [Ollash](https://github.com/ollash) AutoAgentWithTools_\n"
    )
