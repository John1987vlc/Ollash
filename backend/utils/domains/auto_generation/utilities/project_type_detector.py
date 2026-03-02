"""Project type detector — zero LLM calls.

Keyword/regex matching against project description and README text to identify
the intended technology domain. Used by ReadmeGenerationPhase to set
``PhaseContext.project_type_info``, which downstream phases use to enforce
file-extension whitelists and inject type constraints into structure prompts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import FrozenSet, List


@dataclass
class ProjectTypeInfo:
    """Result of a project-type detection pass."""

    project_type: str
    """Short identifier, e.g. ``'frontend_web'``, ``'python_app'``, ``'unknown'``."""

    allowed_extensions: FrozenSet[str]
    """Frozenset of dot-prefixed extensions allowed for this project type."""

    detected_keywords: List[str]
    """Regex patterns that matched (for debugging / blackboard recording)."""

    confidence: float
    """0.0–1.0; values below 0.4 mean the type could not be determined reliably."""


class ProjectTypeDetector:
    """Detect the technology domain of a project from its description and README.

    All methods are class-level utilities — no instance state, no I/O, no LLM calls.

    Usage::

        info = ProjectTypeDetector.detect(project_description, readme_content)
        if info.project_type != "unknown" and info.confidence >= 0.4:
            print(info.allowed_extensions)
    """

    # ---------------------------------------------------------------------------
    # Profile definitions
    # Each profile maps a ``project_type`` key to:
    #   "keywords" — list of regex patterns (matched case-insensitively against
    #                the combined description+README text)
    #   "extensions" — frozenset of allowed dot-prefixed file extensions
    # ---------------------------------------------------------------------------
    _PROFILES: dict[str, dict] = {
        "frontend_web": {
            "keywords": [
                r"\bhtml\b",
                r"\bcss\b",
                r"\bjavascript\b",
                r"\bjs\b",
                r"\bvanilla\s+js\b",
                r"\bvanilla\b",
                r"\bsvg\b",
                r"\bpure\s+html\b",
                r"\bpure\s+web\b",
                r"\bno\s+backend\b",
                r"\bno\s+server\b",
                r"\bstatic\s+site\b",
                r"\bstatic\s+page\b",
                r"\blanding\s+page\b",
                r"\bsingle[\s-]page\b",
                r"\bspa\b",
                r"\bfrontend[\s-]only\b",
                r"\bpure\s+front\b",
            ],
            "extensions": frozenset(
                {
                    ".html",
                    ".css",
                    ".js",
                    ".mjs",
                    ".cjs",
                    ".svg",
                    ".json",
                    ".md",
                    ".txt",
                    ".ico",
                    ".xml",
                    ".webmanifest",
                    ".map",
                    ".min.js",
                    ".min.css",
                }
            ),
        },
        "react_app": {
            "keywords": [
                r"\breact\b",
                r"\bjsx\b",
                r"\bnext\.?js\b",
                r"\bvite\b",
                r"\bcreate[\s-]react[\s-]app\b",
                r"\breact[\s-]dom\b",
            ],
            "extensions": frozenset(
                {
                    ".jsx",
                    ".tsx",
                    ".js",
                    ".ts",
                    ".css",
                    ".scss",
                    ".json",
                    ".md",
                    ".svg",
                    ".html",
                    ".mjs",
                    ".cjs",
                    ".env",
                    ".lock",
                    ".toml",
                }
            ),
        },
        "typescript_app": {
            "keywords": [
                r"\btypescript\b",
                r"\bangular\b",
                r"\bvue\b",
                r"\bnuxt\b",
                r"\btsc\b",
                r"\btsconfig\b",
            ],
            "extensions": frozenset(
                {
                    ".ts",
                    ".tsx",
                    ".js",
                    ".mjs",
                    ".json",
                    ".yaml",
                    ".yml",
                    ".md",
                    ".html",
                    ".css",
                    ".scss",
                    ".env",
                    ".lock",
                    ".toml",
                }
            ),
        },
        "python_app": {
            "keywords": [
                r"\bpython\b",
                r"\bflask\b",
                r"\bdjango\b",
                r"\bfastapi\b",
                r"\bpyproject\b",
                r"\brequirements\.txt\b",
                r"\bpip\b",
                r"\bpyenv\b",
                r"\bpython3\b",
            ],
            "extensions": frozenset(
                {
                    ".py",
                    ".pyi",
                    ".toml",
                    ".cfg",
                    ".ini",
                    ".txt",
                    ".md",
                    ".json",
                    ".yaml",
                    ".yml",
                    ".html",
                    ".css",
                    ".js",
                    ".env",
                    ".lock",
                    ".sql",
                }
            ),
        },
        "go_service": {
            "keywords": [
                r"\bgolang\b",
                r"\bgo\s+service\b",
                r"\bgo\s+api\b",
                r"\bgo\s+module\b",
                r"\bgo\.mod\b",
                r"\bgo\s+microservice\b",
                r"\bginko\b",
                r"\bgorilla\b",
            ],
            "extensions": frozenset(
                {
                    ".go",
                    ".mod",
                    ".sum",
                    ".yaml",
                    ".yml",
                    ".json",
                    ".md",
                    ".env",
                    ".toml",
                    ".sql",
                    ".sh",
                }
            ),
        },
        "rust_project": {
            "keywords": [
                r"\brust\b",
                r"\bcargo\b",
                r"\bcargo\.toml\b",
                r"\brust\s+lang\b",
                r"\btokio\b",
                r"\bactix\b",
            ],
            "extensions": frozenset(
                {
                    ".rs",
                    ".toml",
                    ".md",
                    ".lock",
                    ".yaml",
                    ".yml",
                    ".json",
                    ".sh",
                    ".env",
                }
            ),
        },
        "node_backend": {
            "keywords": [
                r"\bnode\.?js\b",
                r"\bexpress\b",
                r"\bkoa\b",
                r"\bfastify\b",
                r"\bnest\.?js\b",
                r"\brestify\b",
                r"\bnode\s+server\b",
                r"\bnode\s+api\b",
            ],
            "extensions": frozenset(
                {
                    ".js",
                    ".ts",
                    ".json",
                    ".yaml",
                    ".yml",
                    ".md",
                    ".env",
                    ".mjs",
                    ".cjs",
                    ".lock",
                    ".toml",
                    ".sql",
                    ".sh",
                }
            ),
        },
    }

    # Universal fallback — used when confidence < 0.4
    _UNIVERSAL_EXTENSIONS: FrozenSet[str] = frozenset(
        {
            ".py",
            ".pyi",
            ".js",
            ".ts",
            ".jsx",
            ".tsx",
            ".html",
            ".css",
            ".scss",
            ".go",
            ".rs",
            ".java",
            ".json",
            ".yaml",
            ".yml",
            ".md",
            ".txt",
            ".env",
            ".toml",
            ".cfg",
            ".ini",
            ".sh",
            ".svg",
            ".xml",
            ".sql",
            ".lock",
            ".mod",
            ".sum",
        }
    )

    # Common backend/compiled extensions that a pure frontend project should never have
    _COMMON_FORBIDDEN_FOR_FRONTEND = [".py", ".go", ".rs", ".java", ".cpp", ".c", ".rb"]

    @classmethod
    def detect(cls, description: str, readme_content: str = "") -> ProjectTypeInfo:
        """Analyse *description* + *readme_content* and return a :class:`ProjectTypeInfo`.

        Zero LLM calls — pure regex/keyword matching.

        Args:
            description: Raw user-provided project description.
            readme_content: Generated or existing README text (optional but improves accuracy).

        Returns:
            A :class:`ProjectTypeInfo` with detected type, allowed extensions, and confidence.
            When confidence < 0.4 the ``project_type`` is ``"unknown"`` and
            ``allowed_extensions`` is the universal set (safe fallback).
        """
        combined = (description + " " + readme_content).lower()

        scores: dict[str, float] = {}
        matched: dict[str, list[str]] = {}

        for profile_name, profile in cls._PROFILES.items():
            hits: list[str] = []
            for pattern in profile["keywords"]:
                if re.search(pattern, combined, re.IGNORECASE):
                    hits.append(pattern)
            if hits:
                scores[profile_name] = len(hits) / len(profile["keywords"])
                matched[profile_name] = hits

        if not scores:
            return ProjectTypeInfo(
                project_type="unknown",
                allowed_extensions=cls._UNIVERSAL_EXTENSIONS,
                detected_keywords=[],
                confidence=0.0,
            )

        best = max(scores, key=lambda k: scores[k])
        best_confidence = scores[best]

        if best_confidence < 0.10:
            return ProjectTypeInfo(
                project_type="unknown",
                allowed_extensions=cls._UNIVERSAL_EXTENSIONS,
                detected_keywords=matched.get(best, []),
                confidence=best_confidence,
            )

        return ProjectTypeInfo(
            project_type=best,
            allowed_extensions=cls._PROFILES[best]["extensions"],
            detected_keywords=matched[best],
            confidence=best_confidence,
        )

    @classmethod
    def get_forbidden_extensions_text(cls, allowed: FrozenSet[str]) -> str:
        """Return a comma-separated string of common extensions NOT in *allowed*.

        Used to build prompt constraint text like "DO NOT create .py, .go files".

        Args:
            allowed: The frozenset of allowed extensions for the detected project type.

        Returns:
            Comma-separated string of forbidden extensions, or empty string if none.
        """
        forbidden = [ext for ext in cls._COMMON_FORBIDDEN_FOR_FRONTEND if ext not in allowed]
        return ", ".join(forbidden)
