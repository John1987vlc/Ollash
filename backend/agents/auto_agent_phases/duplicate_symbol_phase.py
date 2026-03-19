"""Phase 4d: DuplicateSymbolPhase — zero-LLM duplicate symbol removal.

Runs after ExportValidationPhase, before PatchPhase.

Detects and removes duplicate top-level symbol definitions that arise when
CodeFillPhase generates overlapping code blocks — a common failure mode where
the LLM re-defines a function/class it already emitted (often as a shorter stub).

JavaScript/TypeScript:
  Detects duplicate: function X(), window.X =, class X, const/let/var X
  Keeps the FIRST occurrence (which is usually the complete implementation);
  removes subsequent occurrences (which are usually shorter stubs appended
  when the model ran out of token budget and re-started).
  Guard: does not remove an occurrence that is inside a conditional guard
  (if (typeof X === 'undefined'), if (!window.X), /* istanbul ignore */).

Python:
  Delegates to phase_helpers.deduplicate_python_content() (AST-based, keeps LAST).
  Skips files already processed by CodeFillPhase's I5 deduplication pass
  (tracked via ctx.metrics["deduplication_applied"]).

Sprint 19 improvement.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext

# Patterns for JS/TS top-level declarations
_JS_FUNC_RE = re.compile(r"^(?:async\s+)?function\s+(\w+)\s*[(<]", re.MULTILINE)
_JS_WINDOW_RE = re.compile(r"^window\.(\w+)\s*=", re.MULTILINE)
_JS_CLASS_RE = re.compile(r"^class\s+(\w+)\b", re.MULTILINE)
# const/let/var only at true column-0 (not inside functions)
_JS_TOPLEVEL_VAR_RE = re.compile(r"^(?:const|let|var)\s+(\w+)\s*=", re.MULTILINE)

# Guard patterns: if next-to-last line contains any of these, skip removal
_JS_GUARD_RE = re.compile(
    r"if\s*\(\s*typeof\s+\w|if\s*\(\s*!\s*window\.|/\*\s*istanbul\s+ignore",
    re.IGNORECASE,
)

# Extensions to process
_JS_EXTS = {".js", ".ts", ".jsx", ".tsx"}
_PY_EXTS = {".py"}


class DuplicateSymbolPhase(BasePhase):
    phase_id = "4d"
    phase_label = "Duplicate Symbol"

    def run(self, ctx: PhaseContext) -> None:
        try:
            js_cleaned: Dict[str, List[str]] = {}
            py_cleaned: Dict[str, List[str]] = {}

            for rel_path, content in list(ctx.generated_files.items()):
                ext = Path(rel_path).suffix.lower()
                if ext in _JS_EXTS:
                    result = self._clean_js_duplicates(content, rel_path, ctx)
                    if result:
                        js_cleaned[rel_path] = result
                elif ext in _PY_EXTS:
                    result_py = self._clean_py_duplicates(content, rel_path, ctx)
                    if result_py:
                        py_cleaned[rel_path] = result_py

            ctx.metrics["duplicate_symbols"] = {
                "js_cleaned": js_cleaned,
                "py_cleaned": py_cleaned,
            }
            total = len(js_cleaned) + len(py_cleaned)
            if total:
                ctx.logger.info(
                    f"[DuplicateSymbol] Cleaned {total} file(s): JS/TS={len(js_cleaned)}, Python={len(py_cleaned)}"
                )
            else:
                ctx.logger.info("[DuplicateSymbol] No duplicate symbols found")
        except Exception as e:
            ctx.logger.warning(f"[DuplicateSymbol] Non-fatal error: {e}")

    # ----------------------------------------------------------------
    # JavaScript / TypeScript deduplication
    # ----------------------------------------------------------------

    def _clean_js_duplicates(self, content: str, path: str, ctx: PhaseContext) -> List[str]:
        """Remove duplicate JS/TS top-level declarations. Returns list of removed names."""
        lines = content.splitlines(keepends=True)
        removed_names: List[str] = []

        # Collect all pattern matches: (name, line_index_0based)
        matches: List[tuple[str, int]] = []
        for pattern in (_JS_FUNC_RE, _JS_WINDOW_RE, _JS_CLASS_RE, _JS_TOPLEVEL_VAR_RE):
            for m in pattern.finditer(content):
                name = m.group(1)
                # Map character offset to 0-based line index
                line_idx = content.count("\n", 0, m.start())
                # Only consider true top-level: the line must not start with whitespace
                raw_line = lines[line_idx] if line_idx < len(lines) else ""
                if raw_line and raw_line[0] in (" ", "\t"):
                    continue
                matches.append((name, line_idx))

        # Group by name; find duplicates
        by_name: Dict[str, List[int]] = {}
        for name, line_idx in matches:
            by_name.setdefault(name, []).append(line_idx)

        # Collect ranges to remove (later occurrences); process in reverse order
        ranges_to_remove: List[tuple[int, int]] = []
        for name, line_indices in by_name.items():
            if len(line_indices) < 2:
                continue
            # Keep first; remove all subsequent
            for dup_start_idx in sorted(line_indices[1:], reverse=True):
                # Guard: check the two lines before this occurrence for conditional guards
                guard_window = "".join(lines[max(0, dup_start_idx - 2) : dup_start_idx])
                if _JS_GUARD_RE.search(guard_window):
                    ctx.logger.debug(f"[DuplicateSymbol] Skipped guarded duplicate '{name}' in {path}")
                    continue

                dup_end_idx = self._find_js_block_end(lines, dup_start_idx)
                ranges_to_remove.append((dup_start_idx, dup_end_idx))
                removed_names.append(name)
                ctx.logger.warning(
                    f"[DuplicateSymbol] Removed duplicate '{name}' in {path} "
                    f"(lines {dup_start_idx + 1}–{dup_end_idx + 1})"
                )

        if not ranges_to_remove:
            return []

        # Remove in reverse order (bottom-up) to preserve line indices
        new_lines = list(lines)
        for start, end in sorted(ranges_to_remove, reverse=True):
            del new_lines[start : end + 1]

        new_content = "".join(new_lines)
        self._write_file(ctx, path, new_content)
        return removed_names

    @staticmethod
    def _find_js_block_end(lines: List[str], start_idx: int) -> int:
        """Return the last line index (0-based, inclusive) of a JS top-level block.

        Walks forward until the next un-indented top-level declaration or EOF.
        """
        _TOP = re.compile(r"^(?:async\s+)?function\s+\w|^(?:const|let|var)\s+\w|^class\s+\w|^window\.\w")
        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            if line and line[0] not in (" ", "\t", "\n", "\r") and _TOP.match(line):
                return i - 1
        return len(lines) - 1

    # ----------------------------------------------------------------
    # Python deduplication
    # ----------------------------------------------------------------

    def _clean_py_duplicates(self, content: str, path: str, ctx: PhaseContext) -> List[str]:
        """Deduplicate Python top-level definitions. Returns list of removed names."""
        # Skip files already handled by CodeFillPhase I5 dedup
        already_done = ctx.metrics.get("deduplication_applied", {})
        if path in already_done:
            return []

        try:
            from backend.agents.auto_agent_phases.phase_helpers import deduplicate_python_content
        except ImportError:
            return []

        new_content = deduplicate_python_content(content, path, logger=ctx.logger)
        if new_content == content:
            return []

        self._write_file(ctx, path, new_content)
        # Determine which names were removed by comparing line counts
        return ["(python dedup applied)"]
