"""Service for ingesting an existing project's source files into agent state.

Extracted from ``PhaseContext.ingest_existing_project`` so it can be used
and tested independently of the full ``PhaseContext`` god-object.
"""

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from backend.utils.core.language_utils import LanguageUtils


# Extensions and directories recognised / excluded during ingestion.
_SOURCE_EXTENSIONS = frozenset(
    {
        ".py", ".js", ".jsx", ".ts", ".tsx",
        ".go", ".rs", ".java", ".cpp", ".c",
        ".cs", ".rb", ".php", ".swift", ".kt",
        ".json", ".yaml", ".yml", ".xml",
        ".md", ".txt", ".html", ".css", ".scss", ".less",
    }
)

_EXCLUDE_DIRS = frozenset(
    {
        "__pycache__", ".git", ".venv", "venv", "node_modules",
        ".cache", "dist", "build", ".pytest_cache", ".mypy_cache",
        ".egg-info", ".idea", ".vscode", "target",
    }
)


class ProjectIngestionService:
    """Reads source files from an existing project directory.

    Parameters
    ----------
    file_reader:
        Callable that accepts a *str* path and returns the file content as *str*.
        Typically ``file_manager.read_file``.
    logger:
        An object with ``.info()``, ``.debug()``, ``.warning()``, and
        ``.error()`` methods (e.g. ``AgentLogger``).
    """

    def __init__(
        self,
        file_reader: Callable[[str], str],
        logger: Any,
    ) -> None:
        self._read_file = file_reader
        self._logger = logger

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(
        self,
        project_path: Path,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str], str]:
        """Load all source files from *project_path*.

        Returns
        -------
        Tuple of:
        - ``loaded_files``: mapping of relative path → file content
        - ``structure``: nested directory/file metadata dict
        - ``file_paths``: list of relative path strings (same order as walk)
        - ``readme_content``: contents of README.md (empty string if not found)
        """
        self._logger.info(f"🔍 Ingesting existing project from {project_path}")

        loaded_files: Dict[str, str] = {}
        file_paths: List[str] = []
        readme_content: str = ""

        project_path = Path(project_path)
        if not project_path.exists():
            self._logger.error(f"Project path does not exist: {project_path}")
            return {}, {}, [], ""

        try:
            for root, dirs, files_in_dir in os.walk(project_path):
                dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]

                for file in files_in_dir:
                    file_path = Path(root) / file
                    rel_path = file_path.relative_to(project_path)

                    if file_path.suffix.lower() not in _SOURCE_EXTENSIONS:
                        continue

                    if file.lower() == "readme.md":
                        try:
                            readme_content = self._read_file(str(file_path))
                        except Exception as exc:
                            self._logger.warning(f"Could not read README: {exc}")
                        continue

                    try:
                        content = self._read_file(str(file_path))
                        rel_path_str = str(rel_path).replace("\\", "/")
                        loaded_files[rel_path_str] = content
                        file_paths.append(rel_path_str)
                        self._logger.debug(f"  Loaded: {rel_path_str} ({len(content)} bytes)")
                    except Exception as exc:
                        self._logger.warning(f"Could not load {rel_path}: {exc}")

            structure = self._build_structure(loaded_files)
            self._logger.info(f"✅ Ingested {len(loaded_files)} files from existing project")
            return loaded_files, structure, file_paths, readme_content

        except Exception as exc:
            self._logger.error(f"Error ingesting project: {exc}")
            return {}, {}, [], ""

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_structure(self, files: Dict[str, str]) -> Dict[str, Any]:
        """Reconstruct a nested directory/file metadata dict from *files*."""
        structure: Dict[str, Any] = {}

        for file_path in files:
            parts = Path(file_path).parts
            current = structure

            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            filename = parts[-1] if parts else file_path
            current[filename] = {
                "type": "file",
                "extension": Path(filename).suffix,
                "language": LanguageUtils.infer_language(filename),
            }

        return structure
