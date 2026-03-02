# auto_generation/utilities — lazy exports (PEP 562).
# Heavy sub-modules (chromadb chain) are only loaded on first attribute access.

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .signature_extractor import extract_signatures, extract_signatures_regex
    from .prompt_templates import AutoGenPrompts
    from .project_type_detector import ProjectTypeDetector, ProjectTypeInfo
    from .tech_stack_detector import TechStackDetector
    from .code_patcher import CodePatcher
    from .file_refiner import FileRefiner
    from .sandbox_validator import SandboxValidator
    from .auto_test_generator import TestGenerator

_LAZY: dict[str, tuple[str, str]] = {
    "extract_signatures":       ("signature_extractor",  "extract_signatures"),
    "extract_signatures_regex": ("signature_extractor",  "extract_signatures_regex"),
    "AutoGenPrompts":           ("prompt_templates",      "AutoGenPrompts"),
    "ProjectTypeDetector":      ("project_type_detector", "ProjectTypeDetector"),
    "ProjectTypeInfo":          ("project_type_detector", "ProjectTypeInfo"),
    "TechStackDetector":        ("tech_stack_detector",   "TechStackDetector"),
    "CodePatcher":              ("code_patcher",           "CodePatcher"),
    "FileRefiner":              ("file_refiner",           "FileRefiner"),
    "SandboxValidator":         ("sandbox_validator",      "SandboxValidator"),
    "TestGenerator":            ("auto_test_generator",    "TestGenerator"),
}

__all__ = list(_LAZY)


def __getattr__(name: str) -> object:
    if name in _LAZY:
        mod_rel, attr = _LAZY[name]
        mod = importlib.import_module(f".{mod_rel}", package=__name__)
        val = getattr(mod, attr)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
