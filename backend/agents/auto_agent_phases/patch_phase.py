"""Phase 5: PatchPhase — static analysis + targeted CodePatcher fixes.

Runs ruff (Python) and/or tsc (TypeScript) on the generated project.
For each error, uses CodePatcher.edit_existing_file() to apply a targeted fix.
Max 2 passes, max 10 errors fixed per pass.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict, List

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext

_MAX_PASSES = 2
_MAX_FIXES_PER_PASS = 10
_SUBPROCESS_TIMEOUT = 30


class PatchPhase(BasePhase):
    phase_id = "5"
    phase_label = "Patch"

    def run(self, ctx: PhaseContext) -> None:
        total_fixed = 0

        for pass_num in range(_MAX_PASSES):
            errors = self._collect_static_errors(ctx)
            if not errors:
                ctx.logger.info(f"[Patch] Pass {pass_num + 1}: No errors found")
                break

            ctx.logger.info(f"[Patch] Pass {pass_num + 1}: {len(errors)} errors found")
            fixed = self._fix_errors(ctx, errors[:_MAX_FIXES_PER_PASS])
            total_fixed += fixed
            ctx.logger.info(f"[Patch] Pass {pass_num + 1}: Fixed {fixed} files")

        ctx.metrics["patch_fixes"] = total_fixed

    # ----------------------------------------------------------------
    # Static analysis
    # ----------------------------------------------------------------

    def _collect_static_errors(self, ctx: PhaseContext) -> List[Dict[str, str]]:
        errors: List[Dict[str, str]] = []
        has_python = any(p.endswith(".py") for p in ctx.generated_files)
        has_ts = any(p.endswith((".ts", ".tsx")) for p in ctx.generated_files)

        if has_python:
            errors.extend(self._run_ruff(ctx))
        if has_ts:
            errors.extend(self._run_tsc(ctx))

        return errors

    def _run_ruff(self, ctx: PhaseContext) -> List[Dict[str, str]]:
        """Run ruff and parse JSON output."""
        try:
            result = subprocess.run(
                ["python", "-m", "ruff", "check", "--format=json", "."],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
                cwd=str(ctx.project_root),
            )
            if not result.stdout:
                return []
            raw = json.loads(result.stdout)
            out = []
            for e in raw[:20]:
                filename = e.get("filename", "")
                try:
                    rel = str(Path(filename).relative_to(ctx.project_root))
                except ValueError:
                    rel = filename
                code = e.get("code", "E")
                msg = e.get("message", "")
                row = e.get("location", {}).get("row", "?")
                out.append({"file_path": rel, "error": f"{code}: {msg} (line {row})"})
            return out
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            return []

    def _run_tsc(self, ctx: PhaseContext) -> List[Dict[str, str]]:
        """Run tsc --noEmit and parse text output."""
        try:
            result = subprocess.run(
                ["npx", "tsc", "--noEmit"],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
                cwd=str(ctx.project_root),
            )
            if result.returncode == 0:
                return []
            errors = []
            for line in (result.stdout + result.stderr).splitlines()[:20]:
                if "error TS" in line:
                    parts = line.split("(", 1)
                    file_part = parts[0].strip()
                    errors.append(
                        {
                            "file_path": file_part,
                            "error": line.strip(),
                        }
                    )
            return errors
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []

    # ----------------------------------------------------------------
    # Fixing
    # ----------------------------------------------------------------

    def _fix_errors(self, ctx: PhaseContext, errors: List[Dict[str, str]]) -> int:
        """Apply targeted fixes. Returns count of files patched."""
        fixed = 0
        try:
            from backend.utils.domains.auto_generation.utilities.code_patcher import CodePatcher
        except ImportError:
            try:
                from backend.utils.domains.auto_generation.code_patcher import CodePatcher
            except ImportError:
                ctx.logger.warning("[Patch] CodePatcher not available, skipping fixes")
                return 0

        # Group errors by file
        by_file: Dict[str, List[str]] = {}
        for e in errors:
            fp = e.get("file_path", "")
            if fp:
                by_file.setdefault(fp, []).append(e.get("error", ""))

        for file_path, file_errors in by_file.items():
            current_content = ctx.generated_files.get(file_path, "")
            if not current_content:
                # Try to read from disk
                abs_path = ctx.project_root / file_path
                if abs_path.exists():
                    current_content = abs_path.read_text(encoding="utf-8", errors="replace")
                else:
                    continue

            issues = [{"description": err} for err in file_errors[:5]]
            try:
                patcher = CodePatcher(
                    llm_client=ctx.llm_manager.get_client("coder"),
                    logger=ctx.logger,
                )
                patched = patcher.edit_existing_file(
                    file_path=file_path,
                    current_content=current_content,
                    readme=ctx.project_description[:400],
                    issues_to_fix=issues,
                    edit_strategy="partial",
                )
                if patched and patched != current_content:
                    self._write_file(ctx, file_path, patched)
                    fixed += 1
            except Exception as e:
                ctx.logger.warning(f"[Patch] Failed to patch {file_path}: {e}")

        return fixed
