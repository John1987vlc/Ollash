"""Shared helpers for auto-agent phase implementations.

Centralises the recurring pattern of reading ``project_type_info`` from
``PhaseContext`` and applying extension-based structure filtering so that
each phase does not duplicate the guard/confidence-check logic.
"""

from typing import Any, Dict, Optional

from backend.utils.core.constants import MIN_TYPE_DETECTION_CONFIDENCE


def get_type_info_if_active(context: Any) -> Optional[Any]:
    """Return ``context.project_type_info`` if it meets the confidence threshold.

    Parameters
    ----------
    context:
        A ``PhaseContext`` instance (typed as ``Any`` to avoid circular imports).

    Returns
    -------
    The ``ProjectTypeInfo`` dataclass if a confident detection is available,
    otherwise ``None``.
    """
    info = getattr(context, "project_type_info", None)
    if (
        info is not None
        and info.project_type != "unknown"
        and info.confidence >= MIN_TYPE_DETECTION_CONFIDENCE
    ):
        return info
    return None


def filter_structure_by_type(
    context: Any,
    structure: Dict[str, Any],
    logger: Any = None,
) -> Dict[str, Any]:
    """Filter a structure dict to only allow extensions for the detected project type.

    Parameters
    ----------
    context:
        A ``PhaseContext`` instance.
    structure:
        The project structure dict produced by ``StructureGenerator``.
    logger:
        Optional logger; passed to ``StructureGenerator.filter_structure_by_extensions``
        so that removed files are logged at WARNING level.

    Returns
    -------
    The filtered structure (deep copy) if a project type was detected,
    otherwise the original *structure* object unchanged.
    """
    info = get_type_info_if_active(context)
    if info is None:
        return structure

    from backend.utils.domains.auto_generation.structure_generator import StructureGenerator

    return StructureGenerator.filter_structure_by_extensions(
        structure, set(info.allowed_extensions), logger
    )
