"""
backend/cli/repo_context.py
Manages the current-repo context injected into the CLI agent.

Features:
  - Scans the working directory on startup (structure + key files)
  - Tracks files the user has /add-ed explicitly
  - Renders a concise context block for inclusion in LLM messages
  - Compresses context for small models (≤8B) to stay under token limits
"""

from __future__ import annotations

import re
from pathlib import Path

# Extensions treated as "code" for context injection
_CODE_EXTS = {
    ".py",
    ".ts",
    ".js",
    ".tsx",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".cpp",
    ".c",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".md",
    ".txt",
    ".sh",
    ".bash",
    ".zsh",
    ".dockerfile",
    ".tf",
    ".sql",
}

_IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".ollash",
    "generated_projects",
    ".ruff_cache",
    ".tox",
}

_MAX_FILE_CHARS = 8_000  # per-file cap for context injection
_MAX_TOTAL_CHARS_FULL = 32_000  # full-tier total
_MAX_TOTAL_CHARS_SMALL = 6_000  # ≤8B models


def _is_small_model(model_name: str) -> bool:
    m = re.search(r"(\d+(?:\.\d+)?)b", model_name.lower())
    return bool(m and float(m.group(1)) <= 8.0)


class RepoContext:
    """Lightweight repo indexer and context manager for the CLI."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).resolve()
        self._added_files: dict[str, str] = {}  # path → content
        self._structure: str = ""
        self._model_name: str = "qwen3.5:4b"
        self._scan()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_model(self, model_name: str) -> None:
        self._model_name = model_name

    def add_file(self, path: str | Path) -> str:
        """Read a file and add it to the explicit context. Returns status message."""
        p = Path(path)
        if not p.is_absolute():
            p = self.root / p
        p = p.resolve()
        if not p.exists():
            return f"File not found: {path}"
        if not p.is_file():
            return f"Not a file: {path}"
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            key = str(p.relative_to(self.root))
            self._added_files[key] = content
            return f"Added {key} ({len(content):,} chars)"
        except Exception as e:
            return f"Error reading {path}: {e}"

    def remove_file(self, path: str | Path) -> str:
        p = Path(path)
        key = str(p)
        # Try relative key
        try:
            key = str((self.root / p).resolve().relative_to(self.root))
        except ValueError:
            pass
        if key in self._added_files:
            del self._added_files[key]
            return f"Removed {key} from context"
        return f"{key} was not in context"

    def list_files(self) -> list[str]:
        return list(self._added_files.keys())

    def build_context_block(self) -> str:
        """Return a formatted context string ready for injection into the LLM prompt."""
        small = _is_small_model(self._model_name)
        max_total = _MAX_TOTAL_CHARS_SMALL if small else _MAX_TOTAL_CHARS_FULL

        parts: list[str] = []

        # 1. Repo structure (always)
        if self._structure:
            parts.append(f"## Repository: {self.root.name}\n```\n{self._structure}\n```")

        # 2. Explicitly added files
        total = sum(len(p) for p in parts)
        for rel_path, content in self._added_files.items():
            if total >= max_total:
                parts.append(f"[Context limit reached — {len(self._added_files)} files tracked]")
                break
            budget = min(_MAX_FILE_CHARS, max_total - total)
            snippet = content[:budget]
            if len(content) > budget:
                snippet += f"\n... [{len(content) - budget:,} chars truncated]"
            ext = Path(rel_path).suffix.lstrip(".")
            block = f"## File: {rel_path}\n```{ext}\n{snippet}\n```"
            parts.append(block)
            total += len(block)

        return "\n\n".join(parts)

    def has_context(self) -> bool:
        return bool(self._added_files or self._structure)

    def status(self) -> dict:
        return {
            "root": str(self.root),
            "model": self._model_name,
            "added_files": len(self._added_files),
            "files": list(self._added_files.keys()),
            "structure_lines": len(self._structure.splitlines()),
        }

    def rescan(self) -> None:
        self._scan()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _scan(self) -> None:
        """Build a compact directory tree of the repo root."""
        lines: list[str] = []
        self._walk_tree(self.root, lines, prefix="", depth=0, max_depth=4)
        self._structure = "\n".join(lines)

    def _walk_tree(
        self,
        path: Path,
        lines: list[str],
        prefix: str,
        depth: int,
        max_depth: int,
    ) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        except PermissionError:
            return

        dirs = [e for e in entries if e.is_dir() and e.name not in _IGNORE_DIRS]
        files = [e for e in entries if e.is_file() and e.suffix in _CODE_EXTS]

        # Limit breadth to avoid huge output
        for i, entry in enumerate(dirs[:20]):
            connector = "└── " if (i == len(dirs) - 1 and not files) else "├── "
            lines.append(f"{prefix}{connector}{entry.name}/")
            extension = "    " if connector.startswith("└") else "│   "
            self._walk_tree(entry, lines, prefix + extension, depth + 1, max_depth)

        for i, entry in enumerate(files[:30]):
            connector = "└── " if i == len(files) - 1 else "├── "
            size = ""
            try:
                s = entry.stat().st_size
                size = f" ({s:,}B)" if s < 100_000 else f" ({s // 1024}KB)"
            except OSError:
                pass
            lines.append(f"{prefix}{connector}{entry.name}{size}")
