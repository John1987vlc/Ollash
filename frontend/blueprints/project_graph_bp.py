"""Blueprint for project dependency graph visualization.

Scans project files for import statements and builds a vis.js-compatible
node/edge graph for the project mini-map.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from flask import Blueprint, jsonify

project_graph_bp = Blueprint("project_graph", __name__)

_ollash_root_dir: Path = None


def init_app(app):
    global _ollash_root_dir
    _ollash_root_dir = app.config.get("ollash_root_dir", Path("."))


# Regex patterns for detecting imports
_PY_IMPORT_RE = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.MULTILINE)
_JS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?\s+from\s+['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\))""",
    re.MULTILINE,
)


def _scan_python_imports(content: str) -> List[str]:
    """Extract module names from Python import statements."""
    modules = []
    for match in _PY_IMPORT_RE.finditer(content):
        module = match.group(1) or match.group(2)
        if module:
            modules.append(module)
    return modules


def _scan_js_imports(content: str) -> List[str]:
    """Extract module paths from JS/TS import/require statements."""
    modules = []
    for match in _JS_IMPORT_RE.finditer(content):
        module = match.group(1) or match.group(2)
        if module:
            modules.append(module)
    return modules


def _resolve_module_to_file(
    module: str,
    source_file: str,
    project_files: Set[str],
    lang: str,
) -> str | None:
    """Try to resolve an import module to a project file path."""
    if lang == "python":
        # Convert dotted module to path
        rel_path = module.replace(".", "/")
        candidates = [
            f"{rel_path}.py",
            f"{rel_path}/__init__.py",
        ]
        for candidate in candidates:
            if candidate in project_files:
                return candidate
    elif lang == "javascript":
        if not module.startswith("."):
            return None  # External package
        source_dir = os.path.dirname(source_file)
        resolved = os.path.normpath(os.path.join(source_dir, module)).replace("\\", "/")
        candidates = [
            resolved,
            f"{resolved}.js",
            f"{resolved}.ts",
            f"{resolved}.jsx",
            f"{resolved}.tsx",
            f"{resolved}/index.js",
            f"{resolved}/index.ts",
        ]
        for candidate in candidates:
            if candidate in project_files:
                return candidate
    return None


def _get_file_type_group(filename: str) -> str:
    """Get a vis.js group name based on file extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    groups = {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "jsx": "react",
        "tsx": "react",
        "html": "html",
        "css": "css",
        "json": "config",
        "yml": "config",
        "yaml": "config",
        "toml": "config",
        "md": "docs",
        "txt": "docs",
    }
    return groups.get(ext, "other")


def _get_group_color(group: str) -> str:
    """Get a color for each file type group."""
    colors = {
        "python": "#3572A5",
        "javascript": "#f1e05a",
        "typescript": "#2b7489",
        "react": "#61dafb",
        "html": "#e34c26",
        "css": "#563d7c",
        "config": "#a1a1aa",
        "docs": "#10b981",
        "other": "#71717a",
    }
    return colors.get(group, "#71717a")


@project_graph_bp.route("/api/projects/<project_name>/dependency-graph")
def project_dependency_graph(project_name: str):
    """Build and return a file dependency graph for a project.

    Returns vis.js-compatible { nodes: [...], edges: [...] } format.
    """
    if ".." in project_name or "/" in project_name or "\\" in project_name:
        return jsonify({"status": "error", "message": "Invalid project name."}), 400

    project_dir = _ollash_root_dir / "generated_projects" / project_name
    if not project_dir.exists():
        return jsonify({"status": "error", "message": f"Project '{project_name}' not found."}), 404

    # Collect all project files
    project_files: Set[str] = set()
    file_contents: Dict[str, Tuple[str, str]] = {}  # path -> (content, lang)

    scannable_extensions = {".py", ".js", ".ts", ".jsx", ".tsx"}

    for root_dir, _dirs, files in os.walk(project_dir):
        # Skip common non-source directories
        rel_root = os.path.relpath(root_dir, project_dir).replace("\\", "/")
        if any(
            part.startswith(".") or part in ("node_modules", "__pycache__", "venv", ".venv", "dist", "build")
            for part in rel_root.split("/")
        ):
            continue

        for fname in files:
            rel_path = os.path.relpath(os.path.join(root_dir, fname), project_dir).replace("\\", "/")
            project_files.add(rel_path)

            ext = os.path.splitext(fname)[1].lower()
            if ext in scannable_extensions:
                full_path = os.path.join(root_dir, fname)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    lang = "python" if ext == ".py" else "javascript"
                    file_contents[rel_path] = (content, lang)
                except Exception:
                    pass

    # Build nodes
    nodes: List[Dict[str, Any]] = []
    node_ids: Set[str] = set()

    for file_path in project_files:
        group = _get_file_type_group(file_path)
        short_name = os.path.basename(file_path)
        nodes.append(
            {
                "id": file_path,
                "label": short_name,
                "title": file_path,
                "group": group,
                "color": _get_group_color(group),
            }
        )
        node_ids.add(file_path)

    # Build edges from imports
    edges: List[Dict[str, Any]] = []
    edge_set: Set[Tuple[str, str]] = set()

    for source_path, (content, lang) in file_contents.items():
        if lang == "python":
            imports = _scan_python_imports(content)
        else:
            imports = _scan_js_imports(content)

        for module in imports:
            target = _resolve_module_to_file(module, source_path, project_files, lang)
            if target and target != source_path and (source_path, target) not in edge_set:
                edge_set.add((source_path, target))
                edges.append(
                    {
                        "from": source_path,
                        "to": target,
                        "label": "imports",
                        "arrows": "to",
                    }
                )

    return jsonify(
        {
            "status": "ok",
            "nodes": nodes,
            "edges": edges,
            "total_files": len(nodes),
            "total_dependencies": len(edges),
        }
    )
