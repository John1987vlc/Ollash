"""
CoWork router — workspace filesystem browsing.

Provides a single endpoint to list files in a given local path so the
CoWork frontend can populate its file browser panel.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["cowork"])

_EXCLUDE_DIRS = frozenset(
    {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        ".cache",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
        ".ollash",
    }
)

_DOC_EXTS = frozenset(
    {
        ".md",
        ".txt",
        ".rst",
        ".csv",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".py",
        ".js",
        ".ts",
        ".html",
        ".css",
        ".sh",
        ".pdf",
        ".docx",
    }
)


@router.get("/api/cowork/files")
async def list_cowork_files(path: str = Query(..., max_length=500)) -> dict:
    """List files and immediate sub-directories in a given workspace path.

    Filters out hidden dirs, build artifacts, and non-document file types so
    the returned list stays focused on files the CoWork agent can read.
    """
    root = Path(path).expanduser()

    if not root.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    if not root.is_dir():
        raise HTTPException(status_code=400, detail=f"Not a directory: {path}")

    entries = []
    try:
        for item in sorted(root.iterdir()):
            if item.name.startswith(".") or item.name in _EXCLUDE_DIRS:
                continue
            if item.is_file() and item.suffix.lower() not in _DOC_EXTS:
                continue
            entries.append(
                {
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "path": str(item),
                    "ext": item.suffix.lower() if item.is_file() else "",
                }
            )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=f"Permission denied: {exc}")

    return {"workspace": str(root), "entry_count": len(entries), "entries": entries[:200]}
