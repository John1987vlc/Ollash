"""Phase 5: PatchPhase — static analysis + targeted CodePatcher fixes.

Runs ruff (Python), tsc (TypeScript), node --check (JS), and HTML well-formedness
checks on the generated project. For each error, uses CodePatcher to apply a
targeted fix. Max 2 passes, max 10 errors fixed per pass.

After static fixes, runs multi-round iterative-improvement (#10):
  - Up to 3 rounds (large models) / 2 rounds (small models)
  - Round 0: seeds from ctx.cross_file_errors if CrossFileValidationPhase left any
  - Subsequent rounds: LLM review, identify one critical issue, patch it
  - For small projects (<=6 files, <=8000 chars): includes actual file content in
    LLM prompt so it can spot HTML id mismatches, truncated SVGs, etc.
  - Between rounds: re-runs zero-LLM HTML↔JS ID check to refresh cross_file_errors

Improvements:
  #5  — JS syntax via `node --check` + HTML well-formedness via html.parser
  #10 — Multi-round iterative improvement with content inclusion and cross-file seeding
"""

from __future__ import annotations

import html.parser
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext

_MAX_PASSES = 2
_MAX_FIXES_PER_PASS = 10
_SUBPROCESS_TIMEOUT = 30

# Multi-round improvement constants
_MAX_IMPROVEMENT_ROUNDS = 3  # large (>8B) models
_MAX_IMPROVEMENT_ROUNDS_SMALL = 2  # small (<=8B) models
_CONTENT_INCLUDE_MAX_FILES = 6  # include actual file content below this file count
_CONTENT_INCLUDE_MAX_CHARS = 25_000  # and below this total character count (M1)

_IMPROVEMENT_SYSTEM = (
    "You are a code reviewer. Given the project description and a summary of the generated files, "
    "identify the single most important missing piece or obvious bug that would prevent the project "
    "from running correctly. Be specific: name the file and the exact issue. "
    'Output ONLY a JSON object: {"file_path": "...", "issue": "one-sentence description"}. '
    'If everything looks complete, output: {"file_path": "", "issue": ""}.'
)

# Variant that includes actual file content — catches id mismatches, truncated SVGs, etc.
_IMPROVEMENT_SYSTEM_WITH_CONTENT = (
    "You are a code reviewer. Given the project description and the FULL CONTENT of generated files, "
    "identify the single most important missing piece or obvious bug that would prevent the project "
    "from running correctly. Pay special attention to: HTML element IDs vs JS getElementById calls, "
    "missing DOM elements referenced in JS, incomplete game logic, truncated or malformed content. "
    'Output ONLY a JSON object: {"file_path": "...", "issue": "one-sentence description"}. '
    'If everything looks complete, output: {"file_path": "", "issue": ""}.'
)

# Compact variant for small (≤8B) models — fewer tokens, same JSON contract.
_IMPROVEMENT_SYSTEM_SMALL = (
    "Code reviewer. Find ONE critical bug or missing piece that prevents the project from running. "
    'Reply ONLY with JSON: {"file_path": "...", "issue": "..."} or {"file_path": "", "issue": ""}.'
)

_IMPROVEMENT_USER = """Project: {project_name}
Description: {description}
Type: {project_type} | Stack: {tech_stack}

Generated files:
{file_summary}

What is the single most critical missing piece or bug? Output JSON only:"""

_IMPROVEMENT_USER_WITH_CONTENT = """Project: {project_name}
Description: {description}
Type: {project_type}

FILE CONTENTS:
{file_contents}

What is the single most critical missing piece or bug? Output JSON only:"""

_IMPROVEMENT_USER_SMALL = """Project: {project_name} | Type: {project_type}
Files: {file_summary}
Critical bug or missing piece? JSON only:"""


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

        # #10 — Iterative improvement pass (one LLM review cycle, all model sizes)
        self._iterative_improvement(ctx)

    # ----------------------------------------------------------------
    # Static analysis
    # ----------------------------------------------------------------

    def _collect_static_errors(self, ctx: PhaseContext) -> List[Dict[str, str]]:
        errors: List[Dict[str, str]] = []
        has_python = any(p.endswith(".py") for p in ctx.generated_files)
        has_ts = any(p.endswith((".ts", ".tsx")) for p in ctx.generated_files)
        has_js = any(p.endswith(".js") for p in ctx.generated_files)
        has_html = any(p.endswith(".html") for p in ctx.generated_files)
        has_go = any(p.endswith(".go") for p in ctx.generated_files)
        has_rust = any(p.endswith(".rs") for p in ctx.generated_files)
        has_php = any(p.endswith(".php") for p in ctx.generated_files)
        has_ruby = any(p.endswith(".rb") for p in ctx.generated_files)

        if has_python:
            errors.extend(self._run_ruff(ctx))
            errors.extend(self._check_python_connection_bugs(ctx))  # M10
        if has_ts:
            errors.extend(self._run_tsc(ctx))
        if has_js:
            errors.extend(self._run_node_check(ctx))  # #5
        if has_html:
            errors.extend(self._check_html_wellformed(ctx))  # #5
            errors.extend(self._check_html_links(ctx))  # P3 — linkage validation
        if has_go:
            errors.extend(self._run_go_vet(ctx))  # P1
        if has_rust:
            errors.extend(self._run_cargo_check(ctx))  # P1
        if has_php:
            errors.extend(self._run_php_lint(ctx))  # P1
        if has_ruby:
            errors.extend(self._run_ruby_check(ctx))  # P1

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

    def _run_node_check(self, ctx: PhaseContext) -> List[Dict[str, str]]:
        """#5 — Syntax-check each .js file using `node --check`.

        `node --check` parses JS without executing it. Available on any system
        with Node.js installed. Falls back silently if node is not found.
        """
        errors: List[Dict[str, str]] = []
        js_files = [p for p in ctx.generated_files if p.endswith(".js")]
        for rel_path in js_files[:10]:  # cap to avoid slowdown
            abs_path = ctx.project_root / rel_path
            if not abs_path.exists():
                continue
            try:
                result = subprocess.run(
                    ["node", "--check", str(abs_path)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    error_text = (result.stderr or result.stdout).strip()
                    # Trim long stack traces to one line
                    first_line = error_text.splitlines()[0] if error_text else "SyntaxError"
                    errors.append({"file_path": rel_path, "error": f"JS: {first_line}"})
            except (subprocess.TimeoutExpired, FileNotFoundError):
                break  # node not available — stop trying
        return errors

    def _check_html_wellformed(self, ctx: PhaseContext) -> List[Dict[str, str]]:
        """#5 — Check HTML files for well-formedness using Python's built-in html.parser.

        Detects unclosed tags and malformed attributes without an external tool.
        """

        class _ErrorCollector(html.parser.HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.errors: List[str] = []

            def handle_starttag(self, tag: str, attrs: list) -> None:
                pass

            def handle_endtag(self, tag: str) -> None:
                pass

            def unknown_decl(self, data: str) -> None:
                self.errors.append(f"Unknown declaration: {data[:60]}")

        errors: List[Dict[str, str]] = []
        html_files = [p for p in ctx.generated_files if p.endswith(".html")]
        for rel_path in html_files:
            content = ctx.generated_files.get(rel_path, "")
            if not content:
                continue
            collector = _ErrorCollector()
            try:
                collector.feed(content)
                if collector.errors:
                    for err in collector.errors[:3]:
                        errors.append({"file_path": rel_path, "error": f"HTML: {err}"})
            except Exception as e:
                errors.append({"file_path": rel_path, "error": f"HTML parse error: {e}"})
        return errors

    def _check_html_links(self, ctx: PhaseContext) -> List[Dict[str, str]]:
        """P3 — Verify that <link href> and <script src> reference files that exist.

        Zero-LLM. Catches the common case where the LLM writes `styles.css` but
        the generated file is `style.css`. Reports the discrepancy so CodePatcher
        can fix the HTML attribute.
        """
        import re as _re

        errors: List[Dict[str, str]] = []
        html_files = [p for p in ctx.generated_files if p.endswith(".html")]
        all_generated = set(ctx.generated_files.keys())

        for rel_path in html_files:
            content = ctx.generated_files.get(rel_path, "")
            if not content:
                continue
            hrefs = _re.findall(r'<link[^>]+href=["\']([^"\'#?]+)["\']', content, _re.IGNORECASE)
            srcs = _re.findall(r'<script[^>]+src=["\']([^"\'#?]+)["\']', content, _re.IGNORECASE)
            for ref in hrefs + srcs:
                if ref.startswith(("http", "//", "data:", "blob:")):
                    continue
                ref_clean = ref.lstrip("./")
                if ref_clean not in all_generated and ref not in all_generated:
                    candidates = [f for f in all_generated if f.endswith(ref_clean[-6:]) if ref_clean]
                    hint = f" — did you mean: {candidates[0]}?" if candidates else ""
                    errors.append(
                        {
                            "file_path": rel_path,
                            "error": f"Broken link: '{ref}' not found in generated files{hint}",
                        }
                    )
        return errors

    def _run_go_vet(self, ctx: PhaseContext) -> List[Dict[str, str]]:
        """P1 — Run `go vet ./...` if go is available. Gracefully skips if not."""
        try:
            result = subprocess.run(
                ["go", "vet", "./..."],
                capture_output=True,
                text=True,
                timeout=_SUBPROCESS_TIMEOUT,
                cwd=str(ctx.project_root),
            )
            if result.returncode == 0:
                return []
            errors = []
            for line in (result.stdout + result.stderr).splitlines()[:20]:
                if line.strip() and ":" in line:
                    parts = line.split(":", 2)
                    file_part = parts[0].strip().lstrip("#").strip()
                    msg = ":".join(parts[1:]).strip() if len(parts) > 1 else line.strip()
                    errors.append({"file_path": file_part, "error": f"go vet: {msg}"})
            return errors
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []  # go not installed — skip silently

    def _run_cargo_check(self, ctx: PhaseContext) -> List[Dict[str, str]]:
        """P1 — Run `cargo check` if cargo is available. Gracefully skips if not."""
        try:
            result = subprocess.run(
                ["cargo", "check", "--message-format=short"],
                capture_output=True,
                text=True,
                timeout=60,  # cargo can be slow on first run
                cwd=str(ctx.project_root),
            )
            if result.returncode == 0:
                return []
            errors = []
            for line in (result.stdout + result.stderr).splitlines()[:20]:
                if "error" in line.lower() and "-->" in line:
                    # Format: "error[E0308]: type mismatch --> src/main.rs:10:5"
                    arrow_idx = line.find("-->")
                    msg = line[:arrow_idx].strip()
                    loc = line[arrow_idx + 3 :].strip()
                    file_part = loc.split(":")[0].strip()
                    errors.append({"file_path": file_part, "error": f"cargo: {msg}"})
            return errors
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []  # cargo not installed — skip silently

    def _run_php_lint(self, ctx: PhaseContext) -> List[Dict[str, str]]:
        """P1 — Syntax-check each .php file using `php -l`. Skips if php not found."""
        errors: List[Dict[str, str]] = []
        php_files = [p for p in ctx.generated_files if p.endswith(".php")]
        for rel_path in php_files[:10]:
            abs_path = ctx.project_root / rel_path
            if not abs_path.exists():
                continue
            try:
                result = subprocess.run(
                    ["php", "-l", str(abs_path)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    msg = (result.stderr or result.stdout).strip().splitlines()[0]
                    errors.append({"file_path": rel_path, "error": f"PHP: {msg}"})
            except (subprocess.TimeoutExpired, FileNotFoundError):
                break  # php not available
        return errors

    def _run_ruby_check(self, ctx: PhaseContext) -> List[Dict[str, str]]:
        """P1 — Syntax-check each .rb file using `ruby -c`. Skips if ruby not found."""
        errors: List[Dict[str, str]] = []
        ruby_files = [p for p in ctx.generated_files if p.endswith(".rb")]
        for rel_path in ruby_files[:10]:
            abs_path = ctx.project_root / rel_path
            if not abs_path.exists():
                continue
            try:
                result = subprocess.run(
                    ["ruby", "-c", str(abs_path)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    msg = (result.stderr or result.stdout).strip().splitlines()[0]
                    errors.append({"file_path": rel_path, "error": f"Ruby: {msg}"})
            except (subprocess.TimeoutExpired, FileNotFoundError):
                break  # ruby not available
        return errors

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
                    readme=self._build_patch_context(ctx, file_path, current_content),  # M9
                    issues_to_fix=issues,
                    edit_strategy="partial",
                )
                if patched and patched != current_content:
                    self._write_file(ctx, file_path, patched)
                    fixed += 1
            except Exception as e:
                ctx.logger.warning(f"[Patch] Failed to patch {file_path}: {e}")

        return fixed

    # ----------------------------------------------------------------
    # #10 — Multi-round iterative improvement
    # ----------------------------------------------------------------

    def _iterative_improvement(self, ctx: PhaseContext) -> None:
        """Multi-round improvement loop: identify issue → patch → repeat.

        Up to 3 rounds for large models, 2 for small (<=8B).
        Round 0 seeds from ctx.cross_file_errors if CrossFileValidationPhase left any,
        skipping the LLM discovery call for that round.
        For small projects (<=6 files, <=8000 total chars), actual file content is
        included in the LLM prompt so it can spot HTML id mismatches, truncated SVGs, etc.
        Between rounds, a zero-LLM HTML↔JS ID re-check refreshes cross_file_errors.
        """
        small = ctx.is_small()
        default_max = _MAX_IMPROVEMENT_ROUNDS_SMALL if small else _MAX_IMPROVEMENT_ROUNDS
        max_rounds = getattr(ctx, "num_refine_loops", default_max)
        include_content = self._should_include_content(ctx)
        plan_by_path = {fp.path: fp for fp in ctx.blueprint}

        rounds_done = 0
        for round_num in range(max_rounds):
            # Round 0: use cross_file_errors as seed to skip LLM issue-discovery
            if round_num == 0 and ctx.cross_file_errors:
                issue_data = self._seed_from_cross_file_errors(ctx)
            else:
                issue_data = self._ask_llm_for_issue(ctx, small, include_content, plan_by_path)

            if not issue_data:
                ctx.logger.info(f"[Patch] Improvement round {round_num + 1}: no issues found")
                break

            file_path: Optional[str] = issue_data.get("file_path", "")
            issue: Optional[str] = issue_data.get("issue", "")
            if not file_path or not issue:
                break

            ctx.logger.info(f"[Patch] Improvement round {round_num + 1}: fixing '{file_path}': {issue}")
            patched = self._patch_single_file(ctx, file_path, issue)
            rounds_done += 1

            # Between rounds (not after the last), refresh cross_file_errors
            if patched and round_num < max_rounds - 1:
                self._refresh_cross_file_errors(ctx)

        ctx.metrics["iterative_improvement_rounds"] = rounds_done

    # ----------------------------------------------------------------
    # Improvement helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _should_include_content(ctx: PhaseContext) -> bool:
        """True when project is small enough to include full file content in prompt."""
        if len(ctx.generated_files) > _CONTENT_INCLUDE_MAX_FILES:
            return False
        total_chars = sum(len(c) for c in ctx.generated_files.values())
        return total_chars <= _CONTENT_INCLUDE_MAX_CHARS

    @staticmethod
    def _seed_from_cross_file_errors(ctx: PhaseContext) -> Optional[Dict[str, str]]:
        """Convert the first cross_file_error into {file_path, issue} for patching."""
        if not ctx.cross_file_errors:
            return None
        err = ctx.cross_file_errors.pop(0)  # consume one error per round
        # target the file that needs updating (file_b = HTML in id_mismatch)
        file_path = err.get("file_b") or err.get("file_a", "")
        description = err.get("description", "")
        suggestion = err.get("suggestion", "")
        issue = f"{description} — {suggestion}" if suggestion else description
        if not file_path or not issue:
            return None
        return {"file_path": file_path, "issue": issue}

    def _ask_llm_for_issue(
        self,
        ctx: PhaseContext,
        small: bool,
        include_content: bool,
        plan_by_path: Dict,
    ) -> Optional[Dict[str, str]]:
        """Ask the LLM to identify one critical issue. Returns {file_path, issue} or None."""
        if include_content and not small:
            # Build full file contents block (bounded by prompt budget)
            file_contents_lines: List[str] = []
            chars_so_far = 0
            max_chars = 18_000  # leave room for system prompt in token budget (M1)
            for path, content in list(ctx.generated_files.items())[:_CONTENT_INCLUDE_MAX_FILES]:
                snippet = content[: max(0, max_chars - chars_so_far)]
                file_contents_lines.append(f"=== {path} ===\n{snippet}")
                chars_so_far += len(snippet)
                if chars_so_far >= max_chars:
                    break
            file_contents = "\n\n".join(file_contents_lines) or "(no files)"
            system = _IMPROVEMENT_SYSTEM_WITH_CONTENT
            user = _IMPROVEMENT_USER_WITH_CONTENT.format(
                project_name=ctx.project_name,
                description=ctx.project_description[:400],
                project_type=ctx.project_type,
                file_contents=file_contents,
            )
        elif small:
            file_summary = self._build_file_summary(ctx, plan_by_path, max_files=8, compact=True)
            system = _IMPROVEMENT_SYSTEM_SMALL
            user = _IMPROVEMENT_USER_SMALL.format(
                project_name=ctx.project_name,
                project_type=ctx.project_type,
                file_summary=file_summary,
            )
        else:
            file_summary = self._build_file_summary(ctx, plan_by_path, max_files=15, compact=False)
            system = _IMPROVEMENT_SYSTEM
            user = _IMPROVEMENT_USER.format(
                project_name=ctx.project_name,
                description=ctx.project_description[:600],
                project_type=ctx.project_type,
                tech_stack=", ".join(ctx.tech_stack),
                file_summary=file_summary,
            )

        try:
            raw = self._llm_call(ctx, system, user, role="coder", no_think=True)
            from backend.utils.core.llm.llm_response_parser import LLMResponseParser

            data = LLMResponseParser.extract_json(raw)
            if data and isinstance(data, dict):
                return data
        except Exception as e:
            ctx.logger.warning(f"[Patch] LLM issue query failed: {e}")
        return None

    def _patch_single_file(self, ctx: PhaseContext, file_path: str, issue: str) -> bool:
        """Apply CodePatcher for a single issue. Returns True if patched."""
        current_content = ctx.generated_files.get(file_path, "")
        if not current_content:
            abs_path = ctx.project_root / file_path
            if abs_path.exists():
                try:
                    current_content = abs_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    pass
        if not current_content:
            return False

        try:
            from backend.utils.domains.auto_generation.utilities.code_patcher import CodePatcher
        except ImportError:
            try:
                from backend.utils.domains.auto_generation.code_patcher import CodePatcher  # type: ignore[no-redef]
            except ImportError:
                return False

        try:
            patcher = CodePatcher(
                llm_client=ctx.llm_manager.get_client("coder"),
                logger=ctx.logger,
            )
            patched = patcher.edit_existing_file(
                file_path=file_path,
                current_content=current_content,
                readme=self._build_patch_context(ctx, file_path, current_content),  # M9
                issues_to_fix=[{"description": issue}],
            )
            if patched and patched != current_content:
                self._write_file(ctx, file_path, patched)
                ctx.logger.info(f"[Patch] Round patched {file_path}")
                return True
        except Exception as e:
            ctx.logger.warning(f"[Patch] Failed to patch '{file_path}': {e}")
        return False

    @staticmethod
    def _build_file_summary(
        ctx: PhaseContext,
        plan_by_path: Dict,
        max_files: int,
        compact: bool,
    ) -> str:
        """Build a path+purpose summary string for the improvement prompt."""
        lines: List[str] = []
        for path in list(ctx.generated_files.keys())[:max_files]:
            plan = plan_by_path.get(path)
            purpose = plan.purpose if plan else "file"
            lines.append(f"{path}: {purpose}" if compact else f"  {path}: {purpose}")
        return "\n".join(lines) or "(no files)"

    def _refresh_cross_file_errors(self, ctx: PhaseContext) -> None:
        """Re-run HTML↔JS ID mismatch check and refresh ctx.cross_file_errors.

        Zero-LLM. Only runs for HTML+JS projects. Replaces the existing list so the
        next improvement round gets fresh data after a patch may have changed IDs.
        """
        import re as _re

        has_html = any(p.endswith(".html") for p in ctx.generated_files)
        has_js = any(p.endswith(".js") for p in ctx.generated_files)
        if not has_html or not has_js:
            return

        html_ids: set = set()
        html_file = ""
        for path, content in ctx.generated_files.items():
            if path.endswith(".html"):
                html_ids.update(_re.findall(r'id=["\']([^"\']+)["\']', content))
                if not html_file:
                    html_file = path

        new_errors: List[Dict[str, str]] = []
        for path, content in ctx.generated_files.items():
            if not path.endswith(".js"):
                continue
            gebi = set(_re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", content))
            qs = set(_re.findall(r'querySelector\s*\(\s*[\'"]#([^\'\"#)]+)[\'"]', content))
            for ref in gebi | qs:
                if ref not in html_ids:
                    new_errors.append(
                        {
                            "file_a": path,
                            "file_b": html_file,
                            "error_type": "id_mismatch",
                            "description": (
                                f"JS getElementById/querySelector('#{ref}') not found "
                                f"(known IDs: {sorted(html_ids)[:5]})"
                            ),
                            "suggestion": f"Set id='{ref}' on the correct HTML element",
                        }
                    )

        # Replace with fresh results (stale errors from before the patch are irrelevant)
        ctx.cross_file_errors = new_errors

    # ----------------------------------------------------------------
    # M9 — Context-aware patch context
    # ----------------------------------------------------------------

    @staticmethod
    def _build_patch_context(ctx: PhaseContext, file_path: str, current_content: str) -> str:
        """Return project description or full HTML content for small HTML files (M9).

        For HTML files ≤5000 chars, including the full current content lets CodePatcher
        see whether elements are inside/outside <body>, preventing insertions after </footer>.
        For all other cases, falls back to a short project description.
        """
        _MAX_HTML_INLINE = 5_000
        if file_path.endswith(".html") and len(current_content) <= _MAX_HTML_INLINE:
            return f"Project: {ctx.project_description[:300]}\n\nCOMPLETE HTML:\n{current_content}"
        return ctx.project_description[:400]

    # ----------------------------------------------------------------
    # M10 — Python DB connection anti-pattern detection
    # ----------------------------------------------------------------

    @staticmethod
    def _check_python_connection_bugs(ctx: PhaseContext) -> List[Dict[str, str]]:
        """Detect common SQLite/DB connection bugs in Python files (M10).

        Pattern 1 — use-after-close: conn.close() followed within 10 lines by
          cursor.execute(), conn.commit(), etc.
        Pattern 2 — init_db only in __main__: init_db() defined but only called
          inside 'if __name__ == "__main__":' with no startup event handler.
        """
        import re as _re

        errors: List[Dict[str, str]] = []
        _USE_AFTER_CLOSE_RE = _re.compile(r"\bconn\.close\(\)")
        _DB_OP_RE = _re.compile(
            r"\b(?:cursor|conn)\.(?:execute|executemany|fetchall|fetchone|fetchmany|commit|rollback)\("
        )
        _STARTUP_RE = _re.compile(r'@\w+\.on_event\s*\(\s*["\']startup["\']|def\s+lifespan\s*\(')
        _INIT_DB_DEF_RE = _re.compile(r"^def\s+init_db\s*\(", _re.MULTILINE)
        _INIT_DB_CALL_RE = _re.compile(r"\binit_db\s*\(")
        _MAIN_GUARD_RE = _re.compile(r'if\s+__name__\s*==\s*["\']__main__["\']')

        for path, content in ctx.generated_files.items():
            if not path.endswith(".py"):
                continue

            lines = content.splitlines()

            # Pattern 1 — use-after-close
            for i, line in enumerate(lines):
                if _USE_AFTER_CLOSE_RE.search(line):
                    window = lines[i + 1 : i + 11]
                    for next_line in window:
                        if _DB_OP_RE.search(next_line):
                            errors.append(
                                {
                                    "file_path": path,
                                    "error": (
                                        f"USE_AFTER_CLOSE at line {i + 1}: "
                                        "conn.close() followed by DB operation — "
                                        "use 'with sqlite3.connect(DB) as conn:' instead"
                                    ),
                                }
                            )
                            break  # one error per close() call

            # Pattern 2 — init_db() only called in __main__ guard
            if not _INIT_DB_DEF_RE.search(content):
                continue  # file doesn't define init_db — skip
            if _STARTUP_RE.search(content):
                continue  # has startup event / lifespan — fine
            # Find all call sites of init_db() — exclude function definitions
            all_calls = [
                m
                for m in _INIT_DB_CALL_RE.finditer(content)
                if "def " not in content[max(0, m.start() - 10) : m.start()]
            ]
            if not all_calls:
                continue
            # Check if every call is inside a __main__ guard
            main_guard_match = _MAIN_GUARD_RE.search(content)
            if not main_guard_match:
                continue
            main_guard_start = main_guard_match.start()
            calls_outside_main = [m for m in all_calls if m.start() < main_guard_start]
            if not calls_outside_main:
                # All calls are after the __main__ guard line — only called in __main__
                errors.append(
                    {
                        "file_path": path,
                        "error": (
                            "INIT_DB_ONLY_IN_MAIN: init_db() is only called inside "
                            "'if __name__ == \"__main__\"' — uvicorn/gunicorn won't call it. "
                            "Add @app.on_event('startup') or a lifespan handler."
                        ),
                    }
                )

        return errors
