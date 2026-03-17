"""Phase 6b: SeniorReviewPhase — comprehensive project review + auto-repair loop.

Runs after PatchPhase, before InfraPhase. Wraps the existing SeniorReviewer utility
(which has never been called from the main pipeline) and adds a repair loop:

  for cycle in range(2):
      review → if passed: done
      identify critical/high issues → call CodePatcher per file → repeat

Skipped automatically for small (<=8B) models — the 32K context window call is
too slow and unreliable on a 4B model. For large models this provides the "senior
architect eyes" that catches incomplete game logic, missing handlers, wrong data
flow, etc. that static analysis and single-pass improvement miss.

Token cost: 1-2 LLM calls per cycle × 2 cycles = up to 4 large-context LLM calls.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext

_MAX_REVIEW_CYCLES = 2
_MAX_ISSUES_PER_CYCLE = 5
_CHAR_BUDGET = 20_000  # characters of file content to send to the reviewer
_COMPACT_CONTENT_MAX_FILES = 6  # include file content in compact review if <= this many files
_COMPACT_CONTENT_MAX_CHARS = 20_000  # and total chars <= this


class SeniorReviewPhase(BasePhase):
    phase_id = "6b"
    phase_label = "Senior Review"

    def run(self, ctx: PhaseContext) -> None:
        if ctx.is_small():
            try:
                self._run_compact_review(ctx)
            except Exception as e:
                ctx.logger.warning(f"[SeniorReview] Compact review error (non-fatal): {e}")
            return

        try:
            self._run_review_cycles(ctx)
        except Exception as e:
            ctx.logger.warning(f"[SeniorReview] Unexpected error (non-fatal): {e}")

    # ----------------------------------------------------------------
    # Compact review for small (<=8B) models
    # ----------------------------------------------------------------

    def _run_compact_review(self, ctx: PhaseContext) -> None:
        """Lightweight 2-cycle review using senior_review_compact prompt.

        For small projects (<=6 files, <=20K total chars), includes actual file content
        so the model can spot HTML id mismatches, missing handlers, truncated logic, etc.
        Runs up to 2 repair cycles; exits early if clean or nothing is fixable.
        """
        try:
            from backend.utils.core.llm.prompt_loader import PromptLoader
        except ImportError:
            ctx.logger.warning("[SeniorReview] PromptLoader unavailable — skipping compact review")
            return

        loader = PromptLoader()
        prompts = loader.load_prompt_sync("domains/auto_generation/small_model_prompts.yaml")
        compact = prompts.get("senior_review_compact", {})
        system_tpl = compact.get("system", "")
        user_tpl = compact.get("user", "")
        if not system_tpl or not user_tpl:
            ctx.logger.warning("[SeniorReview] senior_review_compact prompt not found — skipping")
            return

        try:
            from backend.utils.domains.auto_generation.utilities.code_patcher import CodePatcher
        except ImportError:
            ctx.logger.warning("[SeniorReview] CodePatcher unavailable — compact repair skipped")
            return

        total_chars = sum(len(c) for c in ctx.generated_files.values())
        include_content = (
            len(ctx.generated_files) <= _COMPACT_CONTENT_MAX_FILES and total_chars <= _COMPACT_CONTENT_MAX_CHARS
        )

        patcher = CodePatcher(llm_client=ctx.llm_manager.get_client("coder"), logger=ctx.logger)

        for cycle in range(2):
            # Build user message — with actual file content or just names/purposes
            if include_content:
                content_lines: List[str] = []
                chars_used = 0
                for fp_path, fp_content in ctx.generated_files.items():
                    remaining = _COMPACT_CONTENT_MAX_CHARS - chars_used
                    if remaining <= 0:
                        break
                    snippet = fp_content[:remaining]
                    content_lines.append(f"=== {fp_path} ===\n{snippet}")
                    chars_used += len(snippet)
                files_block = "\n\n".join(content_lines) or "(no files)"
                user_msg = f"Project: {ctx.project_name}\nFILE CONTENTS:\n{files_block}\n\nReview and output JSON now."
            else:
                files_summary_lines = []
                for fp in ctx.blueprint[:10]:
                    files_summary_lines.append(f"- {fp.path}: {fp.purpose}")
                files_summary = "\n".join(files_summary_lines) or "(no files)"
                user_msg = user_tpl.format(
                    project_name=ctx.project_name,
                    file_count=len(ctx.generated_files),
                    files_summary=files_summary,
                )

            ctx.logger.info(
                f"[SeniorReview] Compact review cycle {cycle + 1}/2"
                f" ({'with content' if include_content else 'names-only'})..."
            )
            try:
                raw = self._llm_call(
                    ctx,
                    system_tpl.strip(),
                    user_msg.strip(),
                    role="reviewer",
                    no_think=True,
                )
            except Exception as e:
                ctx.logger.warning(f"[SeniorReview] Compact review LLM call failed: {e}")
                break

            # Parse JSON response
            try:
                import json as _json
                import re as _re

                match = _re.search(r"\{.*\}", raw, _re.DOTALL)
                result = _json.loads(match.group(0)) if match else {}
            except Exception:
                result = {}

            status = result.get("status", "unknown")
            summary = result.get("summary", "")
            critical_issues = result.get("critical_issues", [])

            ctx.logger.info(f"[SeniorReview] Compact cycle {cycle + 1}: {status} — {summary}")
            ctx.metrics[f"senior_review_compact_cycle_{cycle + 1}"] = {
                "status": status,
                "summary": summary,
                "issues": critical_issues,
            }

            if status == "passed" or not critical_issues:
                break  # nothing to fix

            # Attempt to fix up to 3 critical issues
            fixed = 0
            for issue_text in critical_issues[:3]:
                if isinstance(issue_text, dict):
                    file_hint = issue_text.get("file", "")
                    desc = issue_text.get("description", str(issue_text))
                else:
                    file_hint = ""
                    desc = str(issue_text)

                # Find the file to patch: exact match, then partial match
                target = file_hint if file_hint in ctx.generated_files else None
                if not target:
                    for fp in ctx.generated_files:
                        if file_hint and file_hint in fp:
                            target = fp
                            break
                if not target:
                    continue

                current_content = ctx.generated_files.get(target, "")
                if not current_content:
                    continue

                try:
                    patched = patcher.edit_existing_file(
                        file_path=target,
                        current_content=current_content,
                        readme=ctx.project_description[:300],
                        issues_to_fix=[{"description": desc}],
                        edit_strategy="search_replace",
                    )
                    if patched and patched != current_content:
                        self._write_file(ctx, target, patched)
                        fixed += 1
                        ctx.logger.info(f"[SeniorReview] Compact fix cycle {cycle + 1}: '{target}'")
                except Exception as e:
                    ctx.logger.warning(f"[SeniorReview] Compact fix failed for '{target}': {e}")

            ctx.logger.info(
                f"[SeniorReview] Compact cycle {cycle + 1}: {fixed}/{len(critical_issues[:3])} issues fixed"
            )
            if fixed == 0:
                break  # nothing fixable — second cycle won't help

    # ----------------------------------------------------------------
    # Review + repair cycles
    # ----------------------------------------------------------------

    def _run_review_cycles(self, ctx: PhaseContext) -> None:
        summary_record: Dict[str, Any] = {"cycles": [], "final_status": "passed"}

        for cycle in range(_MAX_REVIEW_CYCLES):
            ctx.logger.info(f"[SeniorReview] Cycle {cycle + 1}/{_MAX_REVIEW_CYCLES}")

            review_result = self._call_senior_reviewer(ctx, review_attempt=cycle)
            if review_result is None:
                ctx.logger.warning("[SeniorReview] Reviewer returned no result — stopping cycles")
                break

            status = review_result.get("status", "passed")
            summary = review_result.get("summary", "")
            issues: List[Dict[str, Any]] = review_result.get("issues", [])

            cycle_record: Dict[str, Any] = {
                "cycle": cycle + 1,
                "status": status,
                "summary": summary,
                "issues_found": len(issues),
                "issues_fixed": 0,
            }

            if status == "passed":
                ctx.logger.info(f"[SeniorReview] Cycle {cycle + 1}: passed — {summary}")
                summary_record["final_status"] = "passed"
                summary_record["cycles"].append(cycle_record)
                break

            # status == "failed" — fix critical/high severity issues
            actionable = [i for i in issues if i.get("severity") in ("critical", "high")][:_MAX_ISSUES_PER_CYCLE]

            ctx.logger.info(
                f"[SeniorReview] Cycle {cycle + 1}: failed — "
                f"{len(issues)} issues total, {len(actionable)} critical/high to fix"
            )

            fixed = self._fix_issues(ctx, actionable)
            cycle_record["issues_fixed"] = fixed
            summary_record["final_status"] = "failed"
            summary_record["cycles"].append(cycle_record)

            # On last cycle with remaining issues: log warnings but continue best-effort
            if cycle == _MAX_REVIEW_CYCLES - 1:
                remaining_unfixed = len(actionable) - fixed
                if remaining_unfixed > 0:
                    ctx.logger.warning(
                        f"[SeniorReview] {remaining_unfixed} critical/high issues remain "
                        "after all cycles — continuing best-effort"
                    )
                # Log all non-critical issues as info for visibility
                for issue in issues[:8]:
                    sev = issue.get("severity", "?")
                    f = issue.get("file", "?")
                    desc = issue.get("description", "")
                    ctx.logger.info(f"[SeniorReview]   [{sev}] {f}: {desc}")

        ctx.metrics["senior_review"] = summary_record

    # ----------------------------------------------------------------
    # Call the SeniorReviewer utility
    # ----------------------------------------------------------------

    def _call_senior_reviewer(self, ctx: PhaseContext, review_attempt: int) -> Optional[Dict[str, Any]]:
        """Instantiate SeniorReviewer and run a full project review."""
        try:
            from backend.utils.domains.auto_generation.review.senior_reviewer import SeniorReviewer
            from backend.utils.core.llm.llm_response_parser import LLMResponseParser
        except ImportError as e:
            ctx.logger.warning(f"[SeniorReview] Cannot import SeniorReviewer: {e}")
            return None

        # Build lightweight structure from blueprint (no full content here)
        json_structure = {
            "project_type": ctx.project_type,
            "tech_stack": ctx.tech_stack,
            "files": [{"path": fp.path, "purpose": fp.purpose} for fp in ctx.blueprint],
        }

        # Truncate large files to stay within the 32K context window
        files_for_review = self._build_truncated_files(ctx)

        readme = (
            ctx.generated_files.get("README.md", "")
            or ctx.generated_files.get("readme.md", "")
            or ctx.project_description[:600]
        )

        reviewer = SeniorReviewer(
            llm_client=ctx.llm_manager.get_client("coder"),
            logger=ctx.logger,
            response_parser=LLMResponseParser(),
        )

        try:
            return reviewer.perform_review(
                project_description=ctx.project_description,
                project_name=ctx.project_name,
                readme_content=readme,
                json_structure=json_structure,
                current_files=files_for_review,
                review_attempt=review_attempt,
            )
        except Exception as e:
            ctx.logger.warning(f"[SeniorReview] SeniorReviewer.perform_review failed: {e}")
            return None

    @staticmethod
    def _build_truncated_files(ctx: PhaseContext) -> Dict[str, str]:
        """Build files dict for reviewer, respecting a total char budget.

        Small files are included in full; large files get a truncated excerpt
        so the reviewer still knows the file exists and sees its structure.
        """
        result: Dict[str, str] = {}
        chars_used = 0
        for path, content in ctx.generated_files.items():
            remaining = _CHAR_BUDGET - chars_used
            if remaining <= 0:
                # Budget exhausted — include just the filename so reviewer knows it exists
                result[path] = "... [file present, content omitted]"
                continue
            if len(content) <= remaining:
                result[path] = content
                chars_used += len(content)
            else:
                # Include a truncated excerpt with a clear marker
                excerpt = content[:remaining]
                result[path] = excerpt + f"\n... [truncated, {len(content) - remaining} chars omitted]"
                chars_used += remaining
        return result

    # ----------------------------------------------------------------
    # Apply CodePatcher fixes for identified issues
    # ----------------------------------------------------------------

    def _fix_issues(self, ctx: PhaseContext, issues: List[Dict[str, Any]]) -> int:
        """Apply CodePatcher to each file that has issues. Returns count of patched files."""
        try:
            from backend.utils.domains.auto_generation.utilities.code_patcher import CodePatcher
        except ImportError:
            try:
                from backend.utils.domains.auto_generation.code_patcher import CodePatcher  # type: ignore[no-redef]
            except ImportError:
                ctx.logger.warning("[SeniorReview] CodePatcher not available — cannot auto-fix")
                return 0

        # Group issues by file
        by_file: Dict[str, List[Dict[str, Any]]] = {}
        for issue in issues:
            fp = issue.get("file", "")
            if fp:
                by_file.setdefault(fp, []).append(issue)

        patcher = CodePatcher(
            llm_client=ctx.llm_manager.get_client("coder"),
            logger=ctx.logger,
        )

        fixed = 0
        for file_path, file_issues in by_file.items():
            current_content = ctx.generated_files.get(file_path, "")
            if not current_content:
                abs_path = ctx.project_root / file_path
                if abs_path.exists():
                    try:
                        current_content = abs_path.read_text(encoding="utf-8", errors="replace")
                    except OSError:
                        pass
            if not current_content:
                ctx.logger.warning(f"[SeniorReview] Cannot fix '{file_path}': file not found")
                continue

            # Combine all issues for this file into a single patch call
            issues_to_fix = [
                {
                    "description": (
                        f"[{i.get('severity', '?')}] {i.get('description', '')} — {i.get('recommendation', '')}"
                    )
                }
                for i in file_issues
            ]

            try:
                patched = patcher.edit_existing_file(
                    file_path=file_path,
                    current_content=current_content,
                    readme=ctx.project_description[:400],
                    issues_to_fix=issues_to_fix,
                    edit_strategy="search_replace",
                )
                if patched and patched != current_content:
                    self._write_file(ctx, file_path, patched)
                    fixed += 1
                    ctx.logger.info(f"[SeniorReview] Patched '{file_path}' ({len(file_issues)} issue(s) addressed)")
            except Exception as e:
                ctx.logger.warning(f"[SeniorReview] Failed to patch '{file_path}': {e}")

        return fixed
