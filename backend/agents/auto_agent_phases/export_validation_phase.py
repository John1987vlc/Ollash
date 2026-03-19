"""Phase 4c: ExportValidationPhase — zero-LLM export presence check + targeted repair.

Runs after CrossFileValidationPhase, before DuplicateSymbolPhase.

For each file in the blueprint that declares exports, verifies that every declared
symbol name actually appears in the generated content. When symbols are missing:

  - Large models (>8B): calls CodePatcher.inject_missing_function() to add the
    implementation, then verifies the injection succeeded.
  - Small models (≤8B): records the gap in ctx.cross_file_errors so PatchPhase's
    round-0 seed picks it up.

This phase directly addresses the coherence warnings seen in generated projects
(e.g. "declared export 'initGame' not found in generated content").

Sprint 19 improvement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext

# Extensions for which export checking is not meaningful
_SKIP_EXTS = {
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".txt",
    ".env",
    ".gitignore",
    ".cfg",
    ".ini",
    ".lock",
    ".sh",
    ".bash",
    ".sql",
}


class ExportValidationPhase(BasePhase):
    phase_id = "4c"
    phase_label = "Export Validation"

    def run(self, ctx: PhaseContext) -> None:
        try:
            self._run_export_validation(ctx)
        except Exception as e:
            ctx.logger.warning(f"[ExportValidation] Non-fatal error: {e}")

    # ----------------------------------------------------------------
    # Core validation logic
    # ----------------------------------------------------------------

    def _run_export_validation(self, ctx: PhaseContext) -> None:
        if not ctx.blueprint or not ctx.generated_files:
            ctx.logger.info("[ExportValidation] No blueprint or generated files — skipping")
            ctx.metrics["export_validation"] = {"checked": 0, "missing": [], "repaired": 0}
            return

        missing_by_file: Dict[str, List[str]] = {}
        checked = 0

        for plan in ctx.blueprint:
            if not plan.exports:
                continue
            ext = Path(plan.path).suffix.lower()
            if ext in _SKIP_EXTS:
                continue
            content = ctx.generated_files.get(plan.path, "")
            if not content:
                continue

            checked += 1
            for export_name in plan.exports:
                if export_name and export_name not in content:
                    missing_by_file.setdefault(plan.path, []).append(export_name)

        total_missing = sum(len(v) for v in missing_by_file.values())
        if not missing_by_file:
            ctx.metrics["export_validation"] = {"checked": checked, "missing": [], "repaired": 0}
            ctx.logger.info(f"[ExportValidation] All declared exports present ({checked} files checked)")
            return

        ctx.logger.warning(
            f"[ExportValidation] {total_missing} missing export(s) across "
            f"{len(missing_by_file)} file(s): "
            + ", ".join(f"{f}:{n}" for f, names in list(missing_by_file.items())[:3] for n in names[:2])
        )

        is_small = ctx.is_small()
        repaired = 0

        for file_path, names in missing_by_file.items():
            plan = next((fp for fp in ctx.blueprint if fp.path == file_path), None)
            if not plan:
                continue

            if is_small:
                # Small model: push to cross_file_errors for PatchPhase round 0
                for name in names:
                    ctx.cross_file_errors.append(
                        {
                            "file_a": file_path,
                            "file_b": "",
                            "error_type": "missing_export",
                            "description": (
                                f"'{name}' declared in blueprint exports but absent from "
                                f"generated content of {file_path}"
                            ),
                            "suggestion": f"Add a complete implementation of '{name}' to {file_path}",
                        }
                    )
                continue

            # Large model: inject via CodePatcher
            repaired += self._inject_missing_exports(ctx, file_path, names, plan.purpose, plan.key_logic)

        all_missing = [f"{fp}:{name}" for fp, names in missing_by_file.items() for name in names]
        ctx.metrics["export_validation"] = {
            "checked": checked,
            "missing": all_missing,
            "repaired": repaired,
        }
        ctx.logger.info(f"[ExportValidation] {repaired}/{total_missing} missing export(s) repaired")

    # ----------------------------------------------------------------
    # Injection helper (large models only)
    # ----------------------------------------------------------------

    def _inject_missing_exports(
        self,
        ctx: PhaseContext,
        file_path: str,
        names: List[str],
        purpose: str,
        key_logic: str,
    ) -> int:
        """Use CodePatcher to inject missing exports. Returns count of successfully injected symbols."""
        try:
            from backend.utils.domains.auto_generation.utilities.code_patcher import CodePatcher
        except ImportError:
            ctx.logger.warning("[ExportValidation] CodePatcher unavailable — skipping injection")
            return 0

        content = ctx.generated_files.get(file_path, "")
        if not content:
            return 0

        requirement = (
            f"Implement the following missing export(s): {', '.join(repr(n) for n in names)}. "
            f"File purpose: {purpose}. "
            f"Key logic: {key_logic or 'see project description'}. "
            f"These symbols MUST be defined and accessible as top-level exports in {file_path}."
        )
        related_context = ctx.project_description[:300]

        try:
            patcher = CodePatcher(
                llm_client=ctx.llm_manager.get_client("coder"),
                logger=ctx.logger,
            )
            new_content = patcher.inject_missing_function(
                file_path=file_path,
                content=content,
                requirement=requirement,
                related_context=related_context,
            )
        except Exception as e:
            ctx.logger.warning(f"[ExportValidation] Injection failed for {file_path}: {e}")
            return 0

        if not new_content or new_content == content:
            ctx.logger.warning(f"[ExportValidation] Injection for {file_path} returned unchanged content")
            return 0

        # Verify that at least one of the target names was injected
        injected = [n for n in names if n in new_content]
        if not injected:
            ctx.logger.warning(f"[ExportValidation] Injection for {file_path} did not add missing symbols")
            # Fall back to cross_file_errors for PatchPhase
            for name in names:
                ctx.cross_file_errors.append(
                    {
                        "file_a": file_path,
                        "file_b": "",
                        "error_type": "missing_export",
                        "description": f"'{name}' still absent from {file_path} after injection attempt",
                        "suggestion": f"Add complete implementation of '{name}' to {file_path}",
                    }
                )
            return 0

        self._write_file(ctx, file_path, new_content)
        if ctx.run_logger:
            ctx.run_logger.log_file_written(self.phase_id, file_path, len(new_content), "ok", f"injected: {injected}")
        ctx.logger.info(f"[ExportValidation] Injected {injected} into {file_path}")
        return len(injected)
