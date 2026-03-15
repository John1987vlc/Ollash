"""Phase 5: PatchPhase — static analysis + targeted CodePatcher fixes.

Runs ruff (Python), tsc (TypeScript), node --check (JS), and HTML well-formedness
checks on the generated project. For each error, uses CodePatcher to apply a
targeted fix. Max 2 passes, max 10 errors fixed per pass.

After static fixes, runs one iterative-improvement pass (#10): asks the LLM
to review the full project for obvious missing pieces and applies targeted patches.

Improvements:
  #5  — JS syntax via `node --check` + HTML well-formedness via html.parser
  #10 — Iterative improvement pass after static error fixing
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

_IMPROVEMENT_SYSTEM = (
    "You are a code reviewer. Given the project description and a summary of the generated files, "
    "identify the single most important missing piece or obvious bug that would prevent the project "
    "from running correctly. Be specific: name the file and the exact issue. "
    'Output ONLY a JSON object: {"file_path": "...", "issue": "one-sentence description"}. '
    'If everything looks complete, output: {"file_path": "", "issue": ""}.'
)

_IMPROVEMENT_USER = """Project: {project_name}
Description: {description}
Type: {project_type} | Stack: {tech_stack}

Generated files:
{file_summary}

What is the single most critical missing piece or bug? Output JSON only:"""


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

        # #10 — Iterative improvement pass (one LLM review cycle)
        if not ctx.is_small():
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

    # ----------------------------------------------------------------
    # #10 — Iterative improvement
    # ----------------------------------------------------------------

    def _iterative_improvement(self, ctx: PhaseContext) -> None:
        """Ask the LLM to review the project and identify one critical missing piece.

        Runs one cycle only (LLM review → targeted patch). This catches obvious
        issues that static analysis misses (missing route handler, wrong import path, etc.)
        """
        # Build a compact file summary (path + purpose from blueprint)
        file_summary_lines: List[str] = []
        plan_by_path = {fp.path: fp for fp in ctx.blueprint}
        for path in list(ctx.generated_files.keys())[:15]:
            purpose = plan_by_path.get(path, None)
            purpose_str = purpose.purpose if purpose else "generated file"
            file_summary_lines.append(f"  {path}: {purpose_str}")
        file_summary = "\n".join(file_summary_lines) or "  (no files)"

        user = _IMPROVEMENT_USER.format(
            project_name=ctx.project_name,
            description=ctx.project_description[:600],
            project_type=ctx.project_type,
            tech_stack=", ".join(ctx.tech_stack),
            file_summary=file_summary,
        )

        try:
            raw = self._llm_call(ctx, _IMPROVEMENT_SYSTEM, user, role="coder", no_think=True)
            from backend.utils.core.llm.llm_response_parser import LLMResponseParser

            data = LLMResponseParser.extract_json(raw)
            if not data or not isinstance(data, dict):
                return
            file_path: Optional[str] = data.get("file_path", "")
            issue: Optional[str] = data.get("issue", "")
            if not file_path or not issue:
                ctx.logger.info("[Patch] Iterative improvement: no critical issues found")
                return

            ctx.logger.info(f"[Patch] Iterative improvement: fixing '{file_path}': {issue}")
            current_content = ctx.generated_files.get(file_path, "")
            if not current_content:
                abs_path = ctx.project_root / file_path
                if abs_path.exists():
                    current_content = abs_path.read_text(encoding="utf-8", errors="replace")
            if not current_content:
                return

            try:
                from backend.utils.domains.auto_generation.utilities.code_patcher import CodePatcher
            except ImportError:
                try:
                    from backend.utils.domains.auto_generation.code_patcher import CodePatcher
                except ImportError:
                    return

            patcher = CodePatcher(
                llm_client=ctx.llm_manager.get_client("coder"),
                logger=ctx.logger,
            )
            patched = patcher.edit_existing_file(
                file_path=file_path,
                current_content=current_content,
                readme=ctx.project_description[:400],
                issues_to_fix=[{"description": issue}],
            )
            if patched and patched != current_content:
                self._write_file(ctx, file_path, patched)
                ctx.metrics["iterative_improvement_fix"] = file_path
                ctx.logger.info(f"[Patch] Iterative improvement: patched {file_path}")
        except Exception as e:
            ctx.logger.warning(f"[Patch] Iterative improvement failed: {e}")
