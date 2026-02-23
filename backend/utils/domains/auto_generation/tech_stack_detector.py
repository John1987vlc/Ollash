"""
Tech Stack Detector — Automatically detects framework, language and dependency versions
from project manifests (requirements.txt, package.json, pyproject.toml, etc.).

Used by ProjectAnalysisPhase to inject technology-specific context into LLM prompts.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class TechStackInfo:
    """Detected technology stack information for a project."""

    primary_language: str = "unknown"
    framework: str = "unknown"
    framework_version: Optional[str] = None
    runtime_version: Optional[str] = None
    key_dependencies: Dict[str, str] = field(default_factory=dict)
    build_tool: str = "unknown"
    test_framework: str = "unknown"
    prompt_hints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "primary_language": self.primary_language,
            "framework": self.framework,
            "framework_version": self.framework_version,
            "runtime_version": self.runtime_version,
            "key_dependencies": self.key_dependencies,
            "build_tool": self.build_tool,
            "test_framework": self.test_framework,
            "prompt_hints": self.prompt_hints,
        }


class TechStackDetector:
    """Detects the technology stack from project file contents.

    Supports: Python (requirements.txt, pyproject.toml, setup.cfg),
    JavaScript/TypeScript (package.json), Go (go.mod), Rust (Cargo.toml).
    """

    # Framework detection priority order
    _PYTHON_FRAMEWORKS = [
        ("flask", "Flask"),
        ("django", "Django"),
        ("fastapi", "FastAPI"),
        ("tornado", "Tornado"),
        ("aiohttp", "aiohttp"),
        ("starlette", "Starlette"),
    ]
    _JS_FRAMEWORKS = [
        ("next", "Next.js"),
        ("nuxt", "Nuxt.js"),
        ("react", "React"),
        ("vue", "Vue"),
        ("angular", "Angular"),
        ("svelte", "Svelte"),
        ("express", "Express"),
        ("koa", "Koa"),
        ("fastify", "Fastify"),
    ]
    _TEST_FRAMEWORKS = {
        "pytest": "pytest",
        "unittest": "unittest",
        "jest": "Jest",
        "mocha": "Mocha",
        "vitest": "Vitest",
        "jasmine": "Jasmine",
        "go test": "go test",
        "cargo test": "cargo test",
    }
    _BUILD_TOOLS = {
        "poetry": "Poetry",
        "setuptools": "setuptools",
        "flit": "Flit",
        "hatch": "Hatch",
        "webpack": "Webpack",
        "vite": "Vite",
        "rollup": "Rollup",
        "esbuild": "esbuild",
        "cargo": "Cargo",
    }

    def detect(self, files: Dict[str, str]) -> TechStackInfo:
        """Detect tech stack from project file contents.

        Args:
            files: Mapping of file paths to their content strings.

        Returns:
            TechStackInfo populated with detected stack information.
        """
        info = TechStackInfo()
        all_deps: Dict[str, str] = {}

        # Parse each known manifest file
        for path, content in files.items():
            basename = Path(path).name.lower()

            if basename == "requirements.txt":
                deps = self._parse_requirements_txt(content)
                all_deps.update(deps)
                info.primary_language = "python"

            elif basename == "pyproject.toml":
                deps, build_tool, py_version = self._parse_pyproject_toml(content)
                all_deps.update(deps)
                info.primary_language = "python"
                if build_tool:
                    info.build_tool = build_tool
                if py_version:
                    info.runtime_version = py_version

            elif basename == "setup.cfg" or basename == "setup.py":
                deps = self._parse_setup_cfg(content)
                all_deps.update(deps)
                info.primary_language = "python"

            elif basename == "package.json":
                deps, node_version = self._parse_package_json(content)
                all_deps.update(deps)
                if info.primary_language == "unknown":
                    info.primary_language = "javascript"
                if node_version:
                    info.runtime_version = node_version

            elif basename == "go.mod":
                deps = self._parse_go_mod(content)
                all_deps.update(deps)
                info.primary_language = "go"

            elif basename == "cargo.toml":
                deps = self._parse_cargo_toml(content)
                all_deps.update(deps)
                info.primary_language = "rust"

        # Detect framework from aggregated deps
        framework_name, framework_version = self._detect_framework(
            all_deps, info.primary_language
        )
        info.framework = framework_name
        info.framework_version = framework_version

        # Detect test framework
        for dep_key, label in self._TEST_FRAMEWORKS.items():
            if dep_key in all_deps:
                info.test_framework = label
                break

        # Detect build tool
        if info.build_tool == "unknown":
            for dep_key, label in self._BUILD_TOOLS.items():
                if dep_key in all_deps:
                    info.build_tool = label
                    break

        # Keep only top-level deps (first 20)
        info.key_dependencies = dict(list(all_deps.items())[:20])

        # Build human-readable prompt hints
        info.prompt_hints = self._build_prompt_hints(info)

        return info

    # ------------------------------------------------------------------
    # Manifest parsers
    # ------------------------------------------------------------------

    def _parse_requirements_txt(self, content: str) -> Dict[str, str]:
        """Parse pip requirements.txt format."""
        deps: Dict[str, str] = {}
        pattern = re.compile(
            r"^\s*([A-Za-z0-9_\-\.]+)\s*(?:[>=<~!]+\s*([\d\.]+\w*))?",
            re.MULTILINE,
        )
        for match in pattern.finditer(content):
            name = match.group(1).lower().strip()
            version = match.group(2) or ""
            if name and not name.startswith("#"):
                deps[name] = version
        return deps

    def _parse_pyproject_toml(self, content: str) -> Tuple[Dict[str, str], str, str]:
        """Parse pyproject.toml — extract deps, build-backend, python version.

        Uses stdlib tomllib when available (Python 3.11+); falls back to regex.
        """
        deps: Dict[str, str] = {}
        build_tool = ""
        py_version = ""

        try:
            import tomllib  # Python 3.11+

            data = tomllib.loads(content)
            # Poetry
            poetry_deps = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
            for name, ver in poetry_deps.items():
                if name.lower() != "python":
                    deps[name.lower()] = str(ver) if not isinstance(ver, dict) else ""
                else:
                    py_version = str(ver)
            if poetry_deps:
                build_tool = "poetry"

            # PEP 517/621
            pep_deps = data.get("project", {}).get("dependencies", [])
            for dep in pep_deps:
                m = re.match(r"([A-Za-z0-9_\-\.]+)", dep)
                if m:
                    deps[m.group(1).lower()] = ""

            build_backend = data.get("build-system", {}).get("build-backend", "")
            if not build_tool:
                if "flit" in build_backend:
                    build_tool = "flit"
                elif "hatch" in build_backend:
                    build_tool = "hatch"
                elif "setuptools" in build_backend:
                    build_tool = "setuptools"

        except (ImportError, Exception):
            # Regex fallback for older Python versions
            # Find [tool.poetry.dependencies]
            poetry_block = re.search(
                r"\[tool\.poetry\.dependencies\](.*?)(?=\[|\Z)", content, re.DOTALL
            )
            if poetry_block:
                build_tool = "poetry"
                for line in poetry_block.group(1).splitlines():
                    m = re.match(r'\s*([a-z][a-z0-9_\-]+)\s*=\s*["\'^~>=<]*([\d\.]+)', line, re.I)
                    if m:
                        name = m.group(1).lower()
                        if name == "python":
                            py_version = m.group(2)
                        else:
                            deps[name] = m.group(2)

        return deps, build_tool, py_version

    def _parse_setup_cfg(self, content: str) -> Dict[str, str]:
        """Parse setup.cfg install_requires section."""
        deps: Dict[str, str] = {}
        in_requires = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("install_requires"):
                in_requires = True
                continue
            if in_requires:
                if stripped.startswith("[") or (stripped and not stripped.startswith(" ") and "=" in stripped):
                    break
                m = re.match(r"([A-Za-z0-9_\-\.]+)\s*(?:[>=<~!]+\s*([\d\.]+))?", stripped)
                if m and m.group(1):
                    deps[m.group(1).lower()] = m.group(2) or ""
        return deps

    def _parse_package_json(self, content: str) -> Tuple[Dict[str, str], str]:
        """Parse package.json dependencies and node version."""
        deps: Dict[str, str] = {}
        node_version = ""
        try:
            data = json.loads(content)
            for section in ("dependencies", "devDependencies"):
                for name, ver in data.get(section, {}).items():
                    deps[name.lower()] = ver.lstrip("^~>=<")
            node_version = data.get("engines", {}).get("node", "")
        except (json.JSONDecodeError, Exception):
            pass
        return deps, node_version

    def _parse_go_mod(self, content: str) -> Dict[str, str]:
        """Parse go.mod require block."""
        deps: Dict[str, str] = {}
        for line in content.splitlines():
            stripped = line.strip()
            m = re.match(r"([^\s]+)\s+v([\d\.]+)", stripped)
            if m:
                # Use short name (last path segment)
                name = m.group(1).split("/")[-1].lower()
                deps[name] = m.group(2)
        return deps

    def _parse_cargo_toml(self, content: str) -> Dict[str, str]:
        """Parse Cargo.toml [dependencies] section."""
        deps: Dict[str, str] = {}
        in_deps = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == "[dependencies]":
                in_deps = True
                continue
            if in_deps and stripped.startswith("[") and stripped != "[dependencies]":
                break
            if in_deps:
                m = re.match(r'([a-z][a-z0-9_\-]*)\s*=\s*(?:"([\d\.]+)"|\{.*?version\s*=\s*"([\d\.]+)")', stripped, re.I)
                if m:
                    deps[m.group(1).lower()] = m.group(2) or m.group(3) or ""
        return deps

    # ------------------------------------------------------------------
    # Framework / test detection
    # ------------------------------------------------------------------

    def _detect_framework(
        self, deps: Dict[str, str], language: str
    ) -> Tuple[str, Optional[str]]:
        """Return (framework_name, version_or_None) from dep map."""
        candidates = (
            self._PYTHON_FRAMEWORKS if language == "python" else self._JS_FRAMEWORKS
        )
        for dep_key, label in candidates:
            if dep_key in deps:
                version = deps[dep_key] or None
                return label, version
        return "unknown", None

    # ------------------------------------------------------------------
    # Prompt hint builder
    # ------------------------------------------------------------------

    def _build_prompt_hints(self, info: TechStackInfo) -> List[str]:
        """Build human-readable technology hints for LLM prompts."""
        hints: List[str] = []

        # Language hint
        if info.primary_language != "unknown":
            hints.append(f"Primary language: {info.primary_language}")

        # Framework hint
        if info.framework != "unknown":
            ver_str = f" {info.framework_version}" if info.framework_version else ""
            framework_hints = {
                "Flask": f"Flask{ver_str} — use Blueprints, application factory pattern, Flask-Login for auth",
                "Django": f"Django{ver_str} — use CBVs, Django ORM, Django REST Framework for APIs",
                "FastAPI": f"FastAPI{ver_str} — use Pydantic v2 schemas, async endpoints, dependency injection",
                "Express": f"Express{ver_str} — use Router, middleware pattern, async/await",
                "React": f"React{ver_str} — use functional components, hooks, avoid class components",
                "Next.js": f"Next.js{ver_str} — use App Router, Server Components, server actions",
                "Vue": f"Vue{ver_str} — use Composition API, `<script setup>`, Pinia for state",
            }
            hint = framework_hints.get(info.framework, f"{info.framework}{ver_str}")
            hints.append(hint)

        # Test framework hint
        if info.test_framework != "unknown":
            test_hints = {
                "pytest": "pytest — use fixtures, parametrize, @pytest.mark.unit markers, mock with unittest.mock",
                "Jest": "Jest — use describe/it/expect, jest.mock() for modules, async testing with async/await",
                "Mocha": "Mocha — use describe/it, chai assertions, sinon for stubs",
            }
            hints.append(test_hints.get(info.test_framework, f"Tests: {info.test_framework}"))

        # Build tool hint
        if info.build_tool not in ("unknown", ""):
            hints.append(f"Build tool: {info.build_tool}")

        # Python version hint
        if info.runtime_version:
            hints.append(f"Runtime version: {info.runtime_version}")

        return hints
