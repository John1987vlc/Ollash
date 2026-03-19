# Public API — lazy exports for backward compatibility (PEP 562).
# Names remain importable from this package but are only loaded on first access,
# preventing the ~1.3s cold-import cascade caused by chromadb/numpy/grpc.

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

# Used only by type-checkers — no runtime cost.
if TYPE_CHECKING:
    from .planning.project_planner import ProjectPlanner
    from .generation.structure_generator import StructureGenerator
    from .generation.enhanced_file_content_generator import EnhancedFileContentGenerator
    from .utilities.file_refiner import FileRefiner
    from .review.file_completeness_checker import FileCompletenessChecker
    from .review.project_reviewer import ProjectReviewer
    from .utilities.prompt_templates import AutoGenPrompts
    from .utilities.project_type_detector import ProjectTypeDetector, ProjectTypeInfo

_LAZY: dict[str, tuple[str, str]] = {
    "ProjectPlanner": ("planning.project_planner", "ProjectPlanner"),
    "StructureGenerator": ("generation.structure_generator", "StructureGenerator"),
    "EnhancedFileContentGenerator": ("generation.enhanced_file_content_generator", "EnhancedFileContentGenerator"),
    "FileRefiner": ("utilities.file_refiner", "FileRefiner"),
    "FileCompletenessChecker": ("review.file_completeness_checker", "FileCompletenessChecker"),
    "ProjectReviewer": ("review.project_reviewer", "ProjectReviewer"),
    "AutoGenPrompts": ("utilities.prompt_templates", "AutoGenPrompts"),
    "ProjectTypeDetector": ("utilities.project_type_detector", "ProjectTypeDetector"),
    "ProjectTypeInfo": ("utilities.project_type_detector", "ProjectTypeInfo"),
}

__all__ = list(_LAZY)


def __getattr__(name: str) -> object:
    if name in _LAZY:
        mod_rel, attr = _LAZY[name]
        mod = importlib.import_module(f".{mod_rel}", package=__name__)
        val = getattr(mod, attr)
        # Cache in module globals so subsequent accesses are O(1) dict lookups.
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
