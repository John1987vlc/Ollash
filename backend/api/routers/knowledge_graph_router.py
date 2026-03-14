"""Knowledge graph router — project file dependency graph for vis-network visualization."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/knowledge-graph", tags=["knowledge-graph"])


@router.get("/")
async def knowledge_graph_index():
    return {"status": "ok", "endpoints": ["/project"]}


@router.get("/project")
async def get_project_graph(
    project_path: str = Query(".", description="Path to the project directory"),
):
    """Return a vis-network compatible graph of the project's file dependencies.

    Nodes: each .py file in the project.
    Edges: import relationships detected by DependencyGraph.
    """
    try:
        from pathlib import Path

        from backend.core.containers import main_container

        root = Path(project_path).resolve()
        # Restrict traversal to workspace subtree only — never allow arbitrary FS paths.
        _cwd = Path(".").resolve()
        if not root.is_relative_to(_cwd):
            raise HTTPException(status_code=400, detail="project_path must be within the workspace.")
        if not root.exists():
            raise HTTPException(status_code=404, detail="Path not found.")

        dep_graph = main_container.core.analysis.dependency_graph()

        py_files = [
            str(f.relative_to(root))
            for f in root.rglob("*.py")
            if not any(seg in f.parts for seg in (".git", "__pycache__", "node_modules", ".venv"))
        ][:200]

        raw: dict = {}
        if hasattr(dep_graph, "build_from_structure"):
            result = dep_graph.build_from_structure(py_files, str(root))
            raw = result if isinstance(result, dict) else {}
        if not raw and hasattr(dep_graph, "to_dict"):
            raw = dep_graph.to_dict()

        files: list[str] = raw.get("files", py_files)
        dependencies: dict = raw.get("dependencies", {})
        circular: list = raw.get("circular_deps", [])
        generation_order: list = raw.get("generation_order", [])

        nodes = [
            {
                "id": f,
                "label": f.rsplit("/", 1)[-1].rsplit("\\", 1)[-1],
                "title": f,
                "group": f.split("/")[0] if "/" in f else f.split("\\")[0] if "\\" in f else "root",
            }
            for f in files
        ]

        edges = []
        edge_id = 0
        for source, targets in dependencies.items():
            for target in targets or []:
                edges.append({"id": edge_id, "from": source, "to": target, "arrows": "to"})
                edge_id += 1

        return {
            "nodes": nodes,
            "edges": edges,
            "circular_dependencies": circular,
            "generation_order": generation_order,
            "stats": {
                "files": len(nodes),
                "dependencies": len(edges),
                "circular": len(circular),
            },
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to build knowledge graph.")
