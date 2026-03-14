"""Per-session project index for context-aware interactive chat.

When a coding-mode session is created, :class:`ProjectIndex` is instantiated
with the project root. It:

1. Walks the project tree synchronously (fast — no file reads) to produce a
   compact ``file_tree`` string injected into the agent's system prompt.
2. Reads source files and builds a ``RAGContextSelector`` collection in a
   background thread so the agent can perform semantic search with
   ``search_codebase()``.

Usage example::

    idx = ProjectIndex(project_root="/path/to/my-project")
    idx.start_background_index()

    # Later in a tool call:
    results = idx.search("authentication middleware")
"""

import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger("ollash.project_index")

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
        "target",
        ".ollash",
        ".idea",
        ".vscode",
    }
)
_SOURCE_EXTS = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
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
        ".json",
        ".yaml",
        ".yml",
        ".html",
        ".css",
        ".sh",
        ".toml",
    }
)
_MAX_FILE_SIZE = 128 * 1024  # 128 KB — skip large generated files


class ProjectIndex:
    """Lightweight project index for a single interactive chat session.

    Parameters
    ----------
    project_root:
        Absolute path to the user's project directory.
    """

    def __init__(self, project_root: str) -> None:
        self.project_root = Path(project_root)
        self._rag: Optional[Any] = None
        self._ready = threading.Event()
        self._error: Optional[str] = None
        self._index_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_background_index(self) -> None:
        """Kick off RAG indexing in a daemon thread.  Returns immediately."""
        if self._index_thread is not None:
            return  # Already started
        self._index_thread = threading.Thread(
            target=self._build_rag_index,
            name=f"project-index:{self.project_root.name}",
            daemon=True,
        )
        self._index_thread.start()

    def search(self, query: str, max_results: int = 5, wait_secs: float = 8.0) -> str:
        """Semantic search over the project's source files.

        Blocks up to *wait_secs* for the background index to be ready.
        Returns a formatted string suitable for direct inclusion in an
        agent response.

        Args:
            query: Natural-language or keyword search query.
            max_results: Maximum number of fragments to return.
            wait_secs: Seconds to wait for the index before falling back to
                a simple grep-style filename search.

        Returns:
            A human-readable string with the most relevant code excerpts.
        """
        ready = self._ready.wait(timeout=wait_secs)

        if not ready or self._rag is None:
            # Fallback: filename matching
            return self._filename_fallback_search(query, max_results)

        try:
            from backend.utils.core.analysis.scanners.rag_context_selector import RAGContextSelector

            rag: RAGContextSelector = self._rag
            fragments = rag.select_relevant_fragments(query, max_fragments=max_results)
            if not fragments:
                return f"No results for '{query}'."

            lines: List[str] = [f"### Search results for: {query}", ""]
            for frag in fragments:
                lines.append(f"**{frag.file_path}** (lines {frag.start_line}–{frag.end_line})")
                lines.append("```")
                lines.append(frag.content[:600])
                lines.append("```")
                lines.append("")
            return "\n".join(lines)

        except Exception as exc:
            _log.warning(f"RAG search failed: {exc}; falling back to filename search")
            return self._filename_fallback_search(query, max_results)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_source_files(self) -> Dict[str, str]:
        """Walk project tree and read source files (respects size limit)."""
        files: Dict[str, str] = {}
        root = self.project_root

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_DIRS]
            for fname in filenames:
                fpath = Path(dirpath) / fname
                if fpath.suffix.lower() not in _SOURCE_EXTS:
                    continue
                try:
                    if fpath.stat().st_size > _MAX_FILE_SIZE:
                        continue
                    content = fpath.read_text(encoding="utf-8", errors="replace")
                    rel = str(fpath.relative_to(root)).replace("\\", "/")
                    files[rel] = content
                except Exception:
                    pass
        return files

    def _build_rag_index(self) -> None:
        """Background worker: read files and build RAG collection."""
        try:
            from backend.utils.core.analysis.scanners.rag_context_selector import RAGContextSelector

            rag = RAGContextSelector(project_root=self.project_root)
            files = self._collect_source_files()
            if files:
                rag.index_code_fragments(files)
                _log.info(f"ProjectIndex: indexed {len(files)} files for {self.project_root.name}")
            else:
                _log.warning(f"ProjectIndex: no source files found in {self.project_root}")
            self._rag = rag
        except Exception as exc:
            self._error = str(exc)
            _log.warning(f"ProjectIndex: background indexing failed: {exc}")
        finally:
            self._ready.set()

    def _filename_fallback_search(self, query: str, max_results: int) -> str:
        """Simple filename + first-line search when RAG is not ready."""
        query_lower = query.lower()
        hits: List[str] = []

        for dirpath, dirnames, filenames in os.walk(self.project_root):
            dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_DIRS]
            for fname in filenames:
                fpath = Path(dirpath) / fname
                if fpath.suffix.lower() not in _SOURCE_EXTS:
                    continue
                rel = str(fpath.relative_to(self.project_root)).replace("\\", "/")
                if query_lower in rel.lower():
                    hits.append(rel)
                    if len(hits) >= max_results:
                        break
            if len(hits) >= max_results:
                break

        if not hits:
            return f"No files matching '{query}' found (index not ready yet)."
        return "Files matching query:\n" + "\n".join(f"- {h}" for h in hits)
