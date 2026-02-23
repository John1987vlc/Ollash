"""Utility helpers for language detection and file grouping.

Extracted from ``PhaseContext`` so they can be used independently
and tested without constructing the full 34-parameter god-object.
"""

from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Tuple


class LanguageUtils:
    """Pure-static helpers for programming-language inference."""

    _LANGUAGE_MAP: Dict[str, str] = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".cpp": "cpp",
        ".c": "c",
        ".cs": "csharp",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
    }

    _TEST_PATTERNS: Dict[str, Callable[[str], str]] = {
        "python": lambda stem: str(Path("tests") / f"test_{stem}.py"),
        "javascript": lambda stem: str(Path("tests") / f"{stem}.test.js"),
        "typescript": lambda stem: str(Path("tests") / f"{stem}.test.ts"),
        "go": lambda stem: str(Path(stem).parent / f"{stem}_test.go"),
        "rust": lambda stem: str(Path("tests") / f"{stem}.rs"),
        "java": lambda stem: str(Path("src/test/java") / f"{stem}Test.java"),
    }

    @staticmethod
    def infer_language(file_path: str) -> str:
        """Return the language name for *file_path*, or ``"unknown"``."""
        ext = Path(file_path).suffix.lower()
        return LanguageUtils._LANGUAGE_MAP.get(ext, "unknown")

    @staticmethod
    def group_files_by_language(
        files: Dict[str, str],
    ) -> Dict[str, List[Tuple[str, str]]]:
        """Group *(path, content)* pairs by their inferred language.

        Files whose language resolves to ``"unknown"`` are omitted.
        """
        grouped: Dict[str, List[Tuple[str, str]]] = defaultdict(list)
        for rel_path, content in files.items():
            language = LanguageUtils.infer_language(rel_path)
            if language != "unknown":
                grouped[language].append((rel_path, content))
        return dict(grouped)

    @staticmethod
    def get_test_file_path(source_file: str, language: str) -> str:
        """Return a conventional test-file path for *source_file*.

        Falls back to ``tests/test_<stem>`` for unknown languages.
        """
        stem = Path(source_file).stem
        pattern_fn = LanguageUtils._TEST_PATTERNS.get(language, lambda s: str(Path("tests") / f"test_{s}"))
        return pattern_fn(stem)
