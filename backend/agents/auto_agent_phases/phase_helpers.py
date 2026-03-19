"""Shared helpers reused across multiple AutoAgent phases.

Extracted here to break potential circular imports that arise when one phase
class needs to call a utility that lives inside another phase class.
"""

from __future__ import annotations

import ast


def deduplicate_python_content(content: str, path: str, logger=None) -> str:
    """Remove duplicate top-level function/class definitions, keeping the last (most complete).

    I5 — When the LLM produces multiple overlapping code blocks (e.g. two `def get_db()`)
    the second definition silently overrides the first at runtime but causes confusion and
    is often a sign of incomplete generation. We keep the *last* definition (most likely to
    be the complete one) and remove earlier duplicates.

    Extracted from CodeFillPhase._deduplicate_python_content so DuplicateSymbolPhase can
    reuse it without creating a circular import.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return content  # syntax errors handled elsewhere

    lines = content.splitlines(keepends=True)
    seen: dict[str, int] = {}  # name → start lineno of last seen definition
    duplicate_ranges: list[tuple[int, int]] = []  # (start_line, end_line) 1-indexed, to remove

    top_level_nodes = [
        n for n in ast.iter_child_nodes(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]

    for node in top_level_nodes:
        name = node.name
        if name in seen:
            prev_start = seen[name]
            prev_end = node.lineno - 1
            duplicate_ranges.append((prev_start, prev_end))
            if logger:
                logger.warning(
                    f"[Dedup] Duplicate '{name}' in {path}: "
                    f"removed earlier definition (lines {prev_start}–{prev_end}), "
                    f"kept definition at line {node.lineno}"
                )
        seen[name] = node.lineno

    if not duplicate_ranges:
        return content

    # Remove ranges from bottom to top to preserve line numbers
    for start, end in sorted(duplicate_ranges, reverse=True):
        del lines[start - 1 : end]

    return "".join(lines)


def find_js_definition_end(lines: list[str], start_idx: int) -> int:
    """Return the last line index (0-based) of a JS top-level definition.

    Walks forward from start_idx until a new top-level declaration is found or
    the file ends. Used by DuplicateSymbolPhase to locate the block to remove.
    """
    _TOP_LEVEL_RE = __import__("re").compile(
        r"^(?:async\s+)?function\s+\w|^(?:const|let|var)\s+\w|^class\s+\w|^window\.\w",
        __import__("re").MULTILINE,
    )
    end = len(lines) - 1
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        if _TOP_LEVEL_RE.match(line.lstrip()) and lines[i][0] not in (" ", "\t"):
            # new top-level declaration found — previous line is the end
            return i - 1
    return end
