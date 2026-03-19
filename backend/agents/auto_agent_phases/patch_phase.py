"""Phase 5: PatchPhase — static analysis + targeted CodePatcher fixes.

Runs ruff (Python), tsc (TypeScript), node --check (JS), and HTML well-formedness
checks on the generated project. For each error, uses CodePatcher to apply a
targeted fix. Max 2 passes, max `_MAX_FIXES_PER_PASS` errors fixed per pass
(ruff reports up to 50 errors per run).

After static fixes, runs multi-round iterative-improvement (#10):
  - Up to 3 rounds (large models) / 2 rounds (small models)
  - Round 0: seeds from ctx.cross_file_errors if CrossFileValidationPhase left any
  - Subsequent rounds: LLM review, identify one critical issue, patch it
  - For small projects (<=6 files, <=8000 chars): includes actual file content in
    LLM prompt so it can spot HTML id mismatches, truncated SVGs, etc.
  - Between rounds: re-runs ALL zero-LLM CrossFileValidation passes to refresh cross_file_errors (D)

Improvements:
  #5  — JS syntax via `node --check` + HTML well-formedness via html.parser
  #10 — Multi-round iterative improvement with content inclusion and cross-file seeding
"""

from __future__ import annotations

import html.parser
import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext

_MAX_PASSES = 2
_MAX_FIXES_PER_PASS = 10

# #I3 — Exclude the pipeline run log from improvement context (it's metadata, not project source)
_RUN_LOG_FILENAME = "OLLASH_RUN_LOG.md"
_SUBPROCESS_TIMEOUT = 30

# Multi-round improvement constants
_MAX_IMPROVEMENT_ROUNDS = 3  # large (>8B) models
_MAX_IMPROVEMENT_ROUNDS_SMALL = 3  # small (<=8B) models
_CONTENT_INCLUDE_MAX_FILES = 10  # include actual file content below this file count
_CONTENT_INCLUDE_MAX_CHARS = 80_000  # and below this total character count (M1) — #S18: 50K→80K

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

# Focused review aspects: cycle through these whenever the generic reviewer says "no issues".
# Each aspect forces the LLM to check one specific dimension instead of giving a generic "all clear".
_FOCUSED_REVIEW_ASPECTS = [
    "HTML element IDs vs JavaScript getElementById/querySelector — verify every JS DOM lookup has a matching id in HTML",
    "missing DOM container elements — check every element JS creates or references actually exists in HTML",
    "game loop completeness — initialization, event listeners, and state transitions all wired up",
    "event listener connectivity — every button, keydown, and input event has an attached handler",
    "CSS class names consistency — class names used in JS classList must exist in CSS rules",
    "duplicate global function definitions — no two JS files define the same window.* name",
]

_IMPROVEMENT_SYSTEM_FOCUSED = (
    "You are a code reviewer performing a TARGETED review. "
    "Focus ONLY on this specific concern: {aspect}\n"
    "Inspect the provided files for this exact issue. "
    'Output ONLY JSON: {{"file_path": "...", "issue": "..."}} or {{"file_path": "", "issue": ""}}.'
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

        # Pre-pass: py_compile check catches syntax/import errors ruff misses
        smoke_errors = self._smoke_test_python(ctx)
        if smoke_errors:
            ctx.logger.info(f"[Patch] Smoke test: {len(smoke_errors)} syntax error(s) found")
            fixed = self._fix_errors(ctx, smoke_errors)
            total_fixed += fixed

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
    # Smoke test (py_compile)
    # ----------------------------------------------------------------

    @staticmethod
    def _smoke_test_python(ctx: PhaseContext) -> List[Dict[str, str]]:
        """Run py_compile on all .py files to catch syntax errors ruff misses."""
        errors: List[Dict[str, str]] = []
        project_root = ctx.project_root
        for rel_path in ctx.generated_files:
            if not rel_path.endswith(".py"):
                continue
            abs_path = Path(project_root) / rel_path
            if not abs_path.exists():
                continue
            result = subprocess.run(
                ["python", "-m", "py_compile", str(abs_path)],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                msg = (result.stderr or result.stdout).strip()
                errors.append({"file_path": rel_path, "error": f"SyntaxError: {msg}"})
        return errors

    # ----------------------------------------------------------------
    # Static analysis
    # ----------------------------------------------------------------

    @staticmethod
    def _warn_missing_tools(ctx: PhaseContext) -> None:
        """Warn once per run if an expected linter is not installed. #S18b"""
        checks: list[tuple[str, list[str]]] = [
            ("ruff", ["python"]),
            ("node", ["javascript", "typescript", "frontend_web"]),
            ("tsc", ["typescript"]),
        ]
        tech = [t.lower() for t in ctx.tech_stack] + [ctx.project_type.lower()]
        for tool, applies_to in checks:
            if not any(t in tech for t in applies_to):
                continue
            try:
                subprocess.run(
                    [tool, "--version"],
                    capture_output=True,
                    timeout=5,
                )
            except FileNotFoundError:
                ctx.logger.warning(
                    f"[Patch] '{tool}' not found — {'/'.join(applies_to)} errors will not be caught by static analysis"
                )

    def _collect_static_errors(self, ctx: PhaseContext) -> List[Dict[str, str]]:
        self._warn_missing_tools(ctx)
        errors: List[Dict[str, str]] = []
        has_python = any(p.endswith(".py") for p in ctx.generated_files)
        has_ts = any(p.endswith((".ts", ".tsx")) for p in ctx.generated_files)
        has_js = any(p.endswith(".js") for p in ctx.generated_files)
        has_html = any(p.endswith(".html") for p in ctx.generated_files)
        has_go = any(p.endswith(".go") for p in ctx.generated_files)
        has_rust = any(p.endswith(".rs") for p in ctx.generated_files)
        has_php = any(p.endswith(".php") for p in ctx.generated_files)
        has_ruby = any(p.endswith(".rb") for p in ctx.generated_files)
        has_cs = any(p.endswith(".cs") for p in ctx.generated_files)

        if has_python:
            errors.extend(self._run_ruff(ctx))
            errors.extend(self._check_python_connection_bugs(ctx))  # M10
            errors.extend(self._check_duplicate_python_definitions(ctx))  # I2
        if has_html:
            errors.extend(self._check_duplicate_script_tags(ctx))  # I2
        self._check_security_antipatterns(ctx)  # S6-1 — zero-LLM, advisory only
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
        if has_cs:
            errors.extend(self._check_csharp_static(ctx))  # P1

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
            for e in raw[:50]:  # #S18b: 20→50 — was silently dropping errors 21+ in Python projects
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
    # P1 — C# static checks (regex-based, no external tool required)
    # ----------------------------------------------------------------

    def _check_csharp_static(self, ctx: PhaseContext) -> List[Dict[str, str]]:
        """Regex-based static checks for C# files. No dotnet toolchain needed.

        Checks:
        CS-EF001  EF Core RemoveAsync() — does not exist; use Remove()
        CS-REST002 [HttpGet] on a mutation method name — REST convention violation
        CS-DI003  MapControllers() without AddControllers() in Program.cs
        CS-DB004  AddDbContext without EnsureCreated/Migrate (advisory only — not auto-patched)
        """
        import re as _re

        errors: List[Dict[str, str]] = []
        cs_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".cs")}

        # CS-EF001: RemoveAsync() — EF Core API does not have this method
        _REMOVE_ASYNC_RE = _re.compile(r"\.RemoveAsync\s*\(")
        for path, content in cs_files.items():
            if _REMOVE_ASYNC_RE.search(content):
                errors.append(
                    {
                        "file_path": path,
                        "error": (
                            "CS-EF001: EF Core has no RemoveAsync(); "
                            "replace with context.Set.Remove(entity) followed by SaveChangesAsync()"
                        ),
                    }
                )

        # CS-REST002: [HttpGet] on a mutation method name
        _HTTP_GET_MUTATION_RE = _re.compile(
            r"\[HttpGet\][^\n]*\n[^\n]*\b(Update|Delete|Toggle|Set|Mark|Remove|Create|Add)\w*\s*\(",
            _re.IGNORECASE,
        )
        for path, content in cs_files.items():
            m = _HTTP_GET_MUTATION_RE.search(content)
            if m:
                errors.append(
                    {
                        "file_path": path,
                        "error": (
                            f"CS-REST002: [HttpGet] used on mutation method "
                            f"'{m.group(1)}' — use [HttpPost], [HttpPut], [HttpPatch], "
                            f"or [HttpDelete] for state-changing operations"
                        ),
                    }
                )

        # CS-DI003: MapControllers() without AddControllers() in Program.cs
        for path, content in cs_files.items():
            if "Program" not in path:
                continue
            if "MapControllers" in content and "AddControllers" not in content:
                errors.append(
                    {
                        "file_path": path,
                        "error": (
                            "CS-DI003: app.MapControllers() called but "
                            "builder.Services.AddControllers() not found — "
                            "add AddControllers() before app.Build()"
                        ),
                    }
                )

        # CS-DB004 (advisory only): AddDbContext without EnsureCreated/Migrate
        program_files = [p for p in cs_files if "Program" in p]
        if program_files:
            prog = cs_files[program_files[0]]
            if "AddDbContext" in prog and "EnsureCreated" not in prog and "Migrate" not in prog:
                ctx.logger.warning(
                    "[Patch/C#] Program.cs registers DbContext but no EnsureCreated() or "
                    "Migrate() call found — database may not be initialized on startup"
                )
                ctx.errors.append(
                    "CS-DB004 (advisory): Program.cs missing EnsureCreated() or Migrate() "
                    "after AddDbContext() — add db.Database.EnsureCreated() in startup"
                )

        return errors

    # ----------------------------------------------------------------
    # Fixing
    # ----------------------------------------------------------------

    def _fix_errors(self, ctx: PhaseContext, errors: List[Dict[str, str]]) -> int:
        """Apply targeted fixes. Returns count of files patched."""
        fixed = 0
        from backend.utils.domains.auto_generation.utilities.code_patcher import CodePatcher

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
                    edit_strategy="search_replace",
                )
                if patched and patched != current_content:
                    self._write_file(ctx, file_path, patched)
                    if ctx.run_logger:
                        ctx.run_logger.log_file_written(self.phase_id, file_path, len(patched), "ok")
                    fixed += 1
                else:
                    ctx.logger.warning(f"[Patch] Fix produced no change: {file_path} | {file_errors[0][:80]}")
                    ctx.metrics.setdefault("patch_noop_fixes", []).append(file_path)
            except Exception as e:
                ctx.logger.warning(f"[Patch] Failed to patch {file_path}: {e}")

        return fixed

    # ----------------------------------------------------------------
    # #10 — Multi-round iterative improvement
    # ----------------------------------------------------------------

    def _iterative_improvement(self, ctx: PhaseContext) -> None:
        """Multi-round improvement loop: identify issue → patch → repeat.

        Up to max_rounds iterations (default 3). Round 0 seeds from ctx.cross_file_errors
        if CrossFileValidationPhase left any. When the generic reviewer says "no issues",
        subsequent rounds cycle through _FOCUSED_REVIEW_ASPECTS instead of stopping early.
        Between rounds, a full zero-LLM CrossFileValidation re-check refreshes cross_file_errors (D).
        """
        small = ctx.is_small()
        default_max = _MAX_IMPROVEMENT_ROUNDS_SMALL if small else _MAX_IMPROVEMENT_ROUNDS
        max_rounds = getattr(ctx, "num_refine_loops", default_max)
        include_content = self._should_include_content(ctx)
        plan_by_path = {fp.path: fp for fp in ctx.blueprint}

        rounds_done = 0
        clean_generic_count = 0  # consecutive generic "no issues" responses
        focused_clean_count = 0  # consecutive focused-aspect "no issues" responses
        aspect_index = 0  # cycles through _FOCUSED_REVIEW_ASPECTS

        for round_num in range(max_rounds):
            # S5-2: break early when generic + 2 focused aspects all report clean
            if clean_generic_count >= 1 and focused_clean_count >= 2:
                ctx.logger.info("[Patch] Early exit: generic review + 2 focused aspects all clean")
                break

            if ctx.run_logger:
                ctx.run_logger.log_patch_round_start(round_num + 1, max_rounds)

            # Round 0: use cross_file_errors as seed to skip LLM issue-discovery
            if round_num == 0 and ctx.cross_file_errors:
                issue_data = self._seed_from_cross_file_errors(ctx)
            elif clean_generic_count > 0:
                # Generic review already said clean — switch to a focused aspect check
                aspect = _FOCUSED_REVIEW_ASPECTS[aspect_index % len(_FOCUSED_REVIEW_ASPECTS)]
                issue_data = self._ask_llm_for_issue(ctx, small, include_content, plan_by_path, aspect=aspect)
                aspect_index += 1
            else:
                issue_data = self._ask_llm_for_issue(ctx, small, include_content, plan_by_path)

            file_path: Optional[str] = (issue_data or {}).get("file_path", "")
            issue: Optional[str] = (issue_data or {}).get("issue", "")

            if not file_path or not issue:
                clean_generic_count += 1
                if clean_generic_count > 1:
                    focused_clean_count += 1
                ctx.logger.info(
                    f"[Patch] Improvement round {round_num + 1}: no issues found"
                    f" — trying focused aspect next (clean_count={clean_generic_count})"
                )
                if ctx.run_logger:
                    ctx.run_logger.log_patch_round_end(round_num + 1, 0)
                continue  # try a focused aspect instead of stopping early

            issue_type: Optional[str] = (issue_data or {}).get("issue_type")
            ctx.logger.info(f"[Patch] Improvement round {round_num + 1}: fixing '{file_path}': {issue}")
            patched = self._patch_single_file(
                ctx,
                file_path,
                issue,
                issue_type=issue_type,
                run_logger=ctx.run_logger if ctx.run_logger else None,
            )
            rounds_done += 1
            clean_generic_count = 0  # found and fixed something — reset
            focused_clean_count = 0

            if ctx.run_logger:
                ctx.run_logger.log_patch_round_end(round_num + 1, 1 if patched else 0)

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
        """Convert the first cross_file_error into {file_path, issue} for patching.

        I4A — For form_field_mismatch errors, target the HTML file (file_a) rather than
        the Python model (file_b): renaming a form input name is lower-risk than changing
        a Pydantic model field that may be referenced in many endpoint handlers.
        """
        if not ctx.cross_file_errors:
            return None
        err = ctx.cross_file_errors.pop(0)  # consume one error per round
        # I4A: form_field_mismatch → fix HTML (file_a); all others → fix Python/target (file_b)
        err_type = err.get("error_type", "")
        if err_type == "form_field_mismatch":
            file_path = err.get("file_a") or err.get("file_b", "")
        elif err_type in ("id_mismatch", "window_function_mismatch"):
            # I4-rename: prefer the JS/JS-caller file — it needs to be regenerated structurally
            file_path = err.get("file_a") or err.get("file_b", "")
        else:
            file_path = err.get("file_b") or err.get("file_a", "")
        description = err.get("description", "")
        suggestion = err.get("suggestion", "")
        issue = f"{description} — {suggestion}" if suggestion else description
        if not file_path or not issue:
            return None
        result: Dict[str, str] = {"file_path": file_path, "issue": issue}
        # Tag structural renames so _patch_single_file skips SEARCH/REPLACE
        if err_type in ("id_mismatch", "window_function_mismatch"):
            result["issue_type"] = "structural_rename"
        return result

    def _ask_llm_for_issue(
        self,
        ctx: PhaseContext,
        small: bool,
        include_content: bool,
        plan_by_path: Dict,
        aspect: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """Ask the LLM to identify one critical issue. Returns {file_path, issue} or None.

        When aspect is provided (Bug 2 focused review), overrides the system prompt to
        force inspection of one specific concern instead of a generic "any issue" query.
        """
        if include_content:
            # Build full file contents block (bounded by prompt budget)
            file_contents_lines: List[str] = []
            chars_so_far = 0
            max_chars = 36_000  # #S18: 18K→36K — 18K was truncating 5-file projects (~35K chars total)
            for path, content in list(ctx.generated_files.items())[:_CONTENT_INCLUDE_MAX_FILES]:
                if path.endswith(_RUN_LOG_FILENAME):  # #I3
                    continue
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

        # Bug 2 — Override system prompt for focused aspect review
        if aspect:
            system = _IMPROVEMENT_SYSTEM_FOCUSED.format(aspect=aspect)

        try:
            raw = self._llm_call(ctx, system, user, role="coder", no_think=True)
            from backend.utils.core.llm.llm_response_parser import LLMResponseParser

            data = LLMResponseParser.extract_json(raw)
            if data and isinstance(data, dict):
                return data
        except Exception as e:
            ctx.logger.warning(f"[Patch] LLM issue query failed: {e}")
        return None

    def _patch_single_file(
        self,
        ctx: PhaseContext,
        file_path: str,
        issue: str,
        issue_type: Optional[str] = None,
        run_logger=None,
    ) -> bool:
        """Apply CodePatcher for a single issue. Returns True if patched.

        When issue_type is 'structural_rename' (id_mismatch / window_function_mismatch),
        skip SEARCH/REPLACE entirely and go straight to full-file regeneration — ID renames
        require replacing every occurrence and CodePatcher can't reliably do that.
        """
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

        # I4-rename: bypass SEARCH/REPLACE for structural renames (go straight to regen)
        if issue_type == "structural_rename" and len(current_content) <= 12000:
            ctx.logger.info(f"[Patch] I4-rename: bypassing SEARCH/REPLACE for '{file_path}' — direct regeneration")
            return self._regenerate_file_with_fix(ctx, file_path, current_content, issue)

        from backend.utils.domains.auto_generation.utilities.code_patcher import CodePatcher

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
                # Compute diff for run log before writing
                if run_logger:
                    import difflib

                    diff_lines = list(
                        difflib.unified_diff(
                            current_content.splitlines(keepends=True),
                            patched.splitlines(keepends=True),
                            fromfile=file_path,
                            tofile=file_path,
                            n=3,
                        )
                    )
                    run_logger.log_patch_fix(0, file_path, issue, diff_lines[:60], success=True)
                self._write_file(ctx, file_path, patched)
                ctx.logger.info(f"[Patch] Round patched {file_path}")
                return True
            # I4B — patch was no-op: escalate to full-file regeneration for small files
            ctx.logger.info(f"[Patch] I4B Patch no-op for '{file_path}' — escalating to regeneration")
            if run_logger:
                run_logger.log_patch_fix(0, file_path, issue, None, success=False)
        except Exception as e:
            ctx.logger.warning(f"[Patch] Failed to patch '{file_path}': {e}")
            if run_logger:
                run_logger.log_patch_fix(0, file_path, issue, None, success=False)

        # I4B — fallback: full-file regeneration for files ≤12000 chars
        if len(current_content) <= 12000:
            return self._regenerate_file_with_fix(ctx, file_path, current_content, issue)
        return False

    def _regenerate_file_with_fix(
        self,
        ctx: PhaseContext,
        file_path: str,
        current_content: str,
        issue: str,
    ) -> bool:
        """I4B — Regenerate a small file completely when CodePatcher produces a no-op.

        The patch strategy (search/replace) fails when the LLM cannot reproduce exact
        whitespace from a file it hasn't seen. For small files (≤8000 chars) we include
        the full current content and ask for a complete rewrite with the fix applied.
        This makes one extra LLM call but only on failure — it does not affect the happy path.
        """
        system = (
            "You are fixing a specific bug in the following file. "
            f"Known issue: {issue}\n"
            "Output ONLY the complete corrected file content. No explanations. No markdown fences."
        )
        user = (
            f"FILE: {file_path}\n\n"
            f"CURRENT CONTENT:\n{current_content}\n\n"
            "Fix the issue described above and output the complete corrected file."
        )

        # I5 — inject cross-file context so regenerated code uses correct names
        cross_ctx_lines: List[str] = []
        ext = Path(file_path).suffix.lower()
        if ext == ".js":
            for path, content in ctx.generated_files.items():
                if path.endswith(".html"):
                    ids = re.findall(r'id=["\']([^"\']+)["\']', content)
                    if ids:
                        cross_ctx_lines.append(f"Available HTML IDs in {path}: {', '.join(ids[:15])}")
                    html_calls = re.findall(r"window\.\w+\.(\w+)\s*\(", content)
                    if html_calls:
                        cross_ctx_lines.append(f"Function calls in HTML: {', '.join(sorted(set(html_calls)))}")
                    break
        elif ext == ".html":
            for path, content in ctx.generated_files.items():
                if path.endswith(".js"):
                    exports = re.findall(r"window\.(\w+)\s*=", content)
                    if exports:
                        cross_ctx_lines.append(f"JS window exports in {path}: {', '.join(exports[:10])}")
        if cross_ctx_lines:
            user += "\n\nCROSS-FILE CONTEXT:\n" + "\n".join(cross_ctx_lines)
        try:
            raw = self._llm_call(ctx, system, user, role="coder", no_think=True, max_tokens=4096)
            from backend.agents.auto_agent_phases.code_fill_phase import CodeFillPhase

            content = CodeFillPhase._extract_code(raw, file_path)
            if content and content != current_content:
                self._write_file(ctx, file_path, content)
                if ctx.run_logger:
                    ctx.run_logger.log_file_written(
                        self.phase_id, file_path, len(content), "ok", "I4B regeneration fix"
                    )
                ctx.logger.info(f"[Patch] I4B Regenerated '{file_path}' to fix: {issue[:80]}")
                return True
        except Exception as e:
            ctx.logger.warning(f"[Patch] I4B Regeneration failed for '{file_path}': {e}")
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
            if path.endswith(_RUN_LOG_FILENAME):  # #I3
                continue
            plan = plan_by_path.get(path)
            purpose = plan.purpose if plan else "file"
            lines.append(f"{path}: {purpose}" if compact else f"  {path}: {purpose}")
        return "\n".join(lines) or "(no files)"

    def _refresh_cross_file_errors(self, ctx: PhaseContext) -> None:
        """Re-run ALL CrossFileValidation passes and refresh ctx.cross_file_errors.

        D (Sprint 19): Upgraded from HTML↔JS-ID-only to full 11-pass re-validation.
        Zero-LLM. Replaces the existing list so the next improvement round gets
        fresh data after a patch may have fixed or broken cross-file contracts.
        Only runs when the project contains web/JS files (where most contracts live);
        for pure-Python projects this is a no-op.
        """
        has_web = any(p.endswith((".html", ".js", ".ts", ".css", ".jsx", ".tsx", ".py")) for p in ctx.generated_files)
        if not has_web:
            return

        saved = list(ctx.cross_file_errors)
        try:
            from backend.agents.auto_agent_phases.cross_file_validation_phase import (
                CrossFileValidationPhase,
            )

            ctx.cross_file_errors.clear()
            CrossFileValidationPhase()._run_validation(ctx)

            new_errors = [e for e in ctx.cross_file_errors if e not in saved]
            if new_errors:
                ctx.logger.info(f"[Patch] D: CrossFile re-check found {len(new_errors)} new contract violation(s)")
        except Exception as e:
            # Non-fatal: restore previous errors so next round still has something to work with
            ctx.cross_file_errors = saved
            ctx.logger.warning(f"[Patch] D: CrossFile re-check failed (non-fatal): {e}")

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
    # I2 — Zero-LLM duplicate definition detectors
    # ----------------------------------------------------------------

    @staticmethod
    def _check_duplicate_python_definitions(ctx: PhaseContext) -> List[Dict[str, str]]:
        """I2 — Detect duplicate top-level function/class definitions in Python files.

        Duplicate `def foo()` / `class Foo` at module scope silently overwrites the first
        definition and is never caught by ruff or py_compile. Uses AST — zero tokens.
        """
        import ast as _ast

        errors: List[Dict[str, str]] = []
        for path, content in ctx.generated_files.items():
            if not path.endswith(".py"):
                continue
            try:
                tree = _ast.parse(content)
            except SyntaxError:
                continue  # syntax errors handled by smoke test

            seen: dict[str, int] = {}  # name → first lineno
            for node in _ast.iter_child_nodes(tree):
                if not isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
                    continue
                name = node.name
                if name in seen:
                    errors.append(
                        {
                            "file_path": path,
                            "error": (
                                f"DUPLICATE_DEF: '{name}' defined at line {seen[name]} "
                                f"and again at line {node.lineno} — "
                                "remove the duplicate, keep only one complete implementation"
                            ),
                        }
                    )
                else:
                    seen[name] = node.lineno
        return errors

    @staticmethod
    def _check_duplicate_script_tags(ctx: PhaseContext) -> List[Dict[str, str]]:
        """I2 — Detect duplicate <script src="..."> tags in HTML files.

        Loading the same script twice causes functions to be redefined and event
        listeners to fire twice. Zero-LLM regex check.
        """
        import re as _re

        _SCRIPT_SRC_RE = _re.compile(r'<script[^>]+src=["\']([^"\']+)["\']', _re.IGNORECASE)
        errors: List[Dict[str, str]] = []
        for path, content in ctx.generated_files.items():
            if not path.endswith(".html"):
                continue
            seen: dict[str, bool] = {}
            for m in _SCRIPT_SRC_RE.finditer(content):
                src = m.group(1)
                if src in seen:
                    errors.append(
                        {
                            "file_path": path,
                            "error": (f"DUPLICATE_SCRIPT: '{src}' loaded twice — remove the duplicate <script> tag"),
                        }
                    )
                seen[src] = True
        return errors

    # ----------------------------------------------------------------
    # S6-1 — Zero-LLM security anti-pattern scan
    # ----------------------------------------------------------------

    @staticmethod
    def _check_security_antipatterns(ctx: PhaseContext) -> None:
        """Scan generated files for security anti-patterns using regex only.

        Advisory — results go to ctx.errors (visible in logs) but are NOT
        auto-patched because the patterns are too broad for safe auto-fix.
        Zero tokens consumed.
        """
        import re as _re

        _PATTERNS: List[tuple] = [
            # (regex, match_all_files, description)
            (r"hashlib\.(md5|sha1)\s*\(", True, "Weak hash algorithm (md5/sha1) — use sha256+"),
            (r"\beval\s*\(|\bexec\s*\(", True, "eval()/exec() — potential code injection"),
            (r'(password|secret|token)\s*=\s*["\'][^"\']{3,}["\']', True, "Hardcoded credential literal"),
            (r"os\.system\s*\([^)]*\+", True, "os.system() with string concat — command injection risk"),
            (r"random\.seed\s*\(\s*\d+\s*\)", True, "Fixed RNG seed — non-random output"),
            (r"chars\[i\s*%", False, "Sequential charset indexing — not random (use secrets.choice)"),
            (r"input\s*\([^)]*[Pp]ass", True, "input() for password — use getpass.getpass()"),
        ]

        _PASSWD_GEN_SUFFIXES = ("gen", "pass", "crypt", "password", "secret", "token")

        for file_path, content in ctx.generated_files.items():
            for pattern, match_all, desc in _PATTERNS:
                # Pattern 5 (sequential charset) only applies to password-gen-like files
                if not match_all:
                    name_lower = file_path.lower().replace("\\", "/")
                    if not any(s in name_lower for s in _PASSWD_GEN_SUFFIXES):
                        continue
                if _re.search(pattern, content):
                    msg = f"[Security] {file_path}: {desc}"
                    ctx.logger.warning(msg)
                    ctx.errors.append(msg)

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
        # I3 — in-memory SQLite: data lost on restart
        _MEMORY_SQLITE_RE = _re.compile(
            r'sqlite3\.connect\s*\(\s*["\']:memory:["\']'
            r"|sqlite:///\s*:memory:"
            r'|create_engine\s*\(\s*["\']sqlite:///:memory:["\']',
            _re.IGNORECASE,
        )

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

            # Pattern 3 — I3: in-memory SQLite (data lost on restart)
            if _MEMORY_SQLITE_RE.search(content):
                errors.append(
                    {
                        "file_path": path,
                        "error": (
                            "MEMORY_SQLITE: sqlite3.connect(':memory:') or 'sqlite:///:memory:' — "
                            "all data is lost when the server restarts. "
                            "Use a file-based DB: sqlite3.connect('app.db') or 'sqlite:///app.db'"
                        ),
                    }
                )

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
