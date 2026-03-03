"""backend.agents — lazy public API.

PEP 562: names are only imported when first accessed, so importing any
sub-module under backend.agents (e.g. auto_agent_phases.phase_context)
no longer pulls in AutoAgent → CoreAgent → AutomaticLearningSystem → chromadb.
"""
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .auto_agent import AutoAgent
    from .auto_benchmarker import ModelBenchmarker

__all__ = ["AutoAgent", "ModelBenchmarker"]

_LAZY: dict[str, str] = {
    "AutoAgent": ".auto_agent",
    "ModelBenchmarker": ".auto_benchmarker",
}


def __getattr__(name: str) -> object:
    if name in _LAZY:
        mod = importlib.import_module(_LAZY[name], package=__name__)
        obj = getattr(mod, name)
        globals()[name] = obj  # cache so subsequent accesses are O(1)
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
