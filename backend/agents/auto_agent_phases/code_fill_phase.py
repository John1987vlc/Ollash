"""Phase 4: CodeFillPhase — core file content generation.

Processes files in priority order (set by BlueprintPhase).
Per-file token budget:
  System prompt:      ~800 tokens  (role + rules)
  Plan entry:         ~200 tokens  (path/purpose/exports/imports/key_logic)
  Signature context:  ~500 tokens  (signatures of max 3 dependency files)
  Previous summary:   ~300 tokens  (last generated file — coherence anchor)
  Generation:        ~2000 tokens
  Total:             ~3800 tokens  (fits in 4K window)

Non-code files (JSON, YAML, MD, .env, etc.) use a lightweight config prompt.
Python files are syntax-validated immediately; one retry on failure.

Improvements:
  #2  — Post-generation coherence validation (export name check, zero-LLM)
  #4  — Smart retry: injects actual ruff/ast error into the retry prompt
  #7  — Parallel generation: independent files (same priority group) run in threads
  #8  — Blueprint-hash cache: skips generation when project was already generated
  #13 — SSE event emitted per file as soon as it is written
"""

from __future__ import annotations

import ast
import concurrent.futures
import hashlib
import json
import re
import threading
from pathlib import Path
from typing import List, Optional

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import FilePlan, PhaseContext

_NON_CODE_EXTS = {
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
}

_SYSTEM_FULL = """# ROLE
Expert {language} developer. Generate complete, functional source code.

# RULES
- FORBIDDEN: TODO comments, pass (unless abstract method), ..., raise NotImplementedError, placeholder comments like "# implement this"
- Write real, working implementations
- Follow {language} idioms and best practices
- Use type hints / type annotations everywhere
- Output ONLY the file content. No explanations. No markdown fences."""

_SYSTEM_SMALL = """# ROLE
{language} developer. Write working code.

# RULES
- No TODO, no placeholders, no pass with empty body
- Output code only — no explanations, no markdown"""

_SYSTEM_HTML = """# ROLE
Expert frontend developer. Generate complete, semantic HTML5.

# RULES
- DOCTYPE html, charset + viewport meta tags mandatory
- FORBIDDEN: placeholder comments, empty sections, TODOs, "implement this"
- Use semantic elements: header, main, nav, section, article, footer
- Load CSS with <link rel="stylesheet" href="...">, load JS with <script src="..." defer>
- Output ONLY the HTML content. No explanations. No markdown fences."""

_SYSTEM_CSS = """# ROLE
Expert CSS developer. Generate a complete, working stylesheet.

# RULES
- FORBIDDEN: empty rule blocks, TODO comments, placeholder comments
- Use CSS custom properties (--var-name) for colors and spacing
- Use flexbox or grid for layout
- Output ONLY the CSS content. No explanations. No markdown fences."""

_SYSTEM_BROWSER_JS = """# ROLE
Browser-side JavaScript developer. Write complete ES6+ code for browser execution.

# RULES
- FORBIDDEN: require(), module.exports, TODO comments, placeholder comments, empty functions
- Browser globals available: document, window, navigator, localStorage, fetch, setTimeout, setInterval
- FORBIDDEN: Node.js globals: process, __dirname, Buffer, global
- Expose functions via window.functionName = ... or define them in global scope (scripts loaded via <script> tags, not ES modules)
- Output ONLY the JS content. No explanations. No markdown fences."""

_SYSTEM_BROWSER_JS_SMALL = """# ROLE
Browser JavaScript developer. Write working code for browser execution.

# RULES
- No require(), no module.exports — browser scripts only
- Use document, window, fetch — no Node.js globals
- Expose functions on window.* so HTML can call them
- Output code only, no markdown"""

_SYSTEM_GO = """# ROLE
Expert Go developer. Write idiomatic, production-quality Go code.

# RULES
- Package declaration mandatory at top (package main for executables, package <name> for libraries)
- Group imports: stdlib / external / internal separated by blank lines; remove unused imports
- Use Go naming: CamelCase exported, camelCase unexported, ALL_CAPS constants
- Explicit error handling: if err != nil { return ..., err } — never ignore errors
- Use interfaces for abstraction; structs + methods over inheritance
- Goroutines need sync (WaitGroup, channel, mutex); always close channels
- FORBIDDEN: panic() on expected errors, fmt.Println in production (use log), global mutable state
- Output ONLY the Go file content. No explanations. No markdown fences."""

_SYSTEM_RUST = """# ROLE
Expert Rust developer. Write safe, idiomatic Rust code that compiles.

# RULES
- All use statements at top; only import what is used
- Prefer Result<T, E> for fallible functions; use ? operator for propagation
- Respect ownership: clone() only when necessary, prefer &T and &mut T
- Use #[derive(Debug, Clone, PartialEq)] on data structs where appropriate
- Match arms must be exhaustive; use _ => {} only when intentional
- FORBIDDEN: unwrap()/expect() on production paths, unsafe{} without comment, todo!() without reason
- Output ONLY the Rust file content. No explanations. No markdown fences."""

_SYSTEM_JAVA = """# ROLE
Expert Java developer. Write clean, idiomatic Java code.

# RULES
- Package declaration at top; add ALL necessary import statements
- One public class per file; filename MUST match the public class name exactly
- Use proper access modifiers: private fields, public/protected methods
- Handle checked exceptions: catch specific types, never swallow with empty catch
- Use @Override for overridden methods; use generics to avoid raw types
- FORBIDDEN: System.out.println in production (use Logger), raw types, empty catch blocks, TODO stubs
- Output ONLY the Java file content. No explanations. No markdown fences."""

_SYSTEM_CSHARP = """# ROLE
Expert C# developer. Write clean, idiomatic C# code.

# RULES
- Namespace and all necessary using statements at top
- PascalCase for types/methods/properties; camelCase for local variables/parameters
- Prefer async/await for all I/O; return Task<T> not void for async methods
- Use LINQ for collection transformations; null-conditional ?. and ?? operators
- Dispose IDisposable with using statements or using declarations
- FORBIDDEN: NotImplementedException (implement it), empty catch, Thread.Sleep in async code
- Output ONLY the C# file content. No explanations. No markdown fences."""

_SYSTEM_SVG = """# ROLE
SVG graphic designer. Generate complete, well-structured SVG markup.

# RULES
- Root <svg> must have xmlns="http://www.w3.org/2000/svg", viewBox, width, height
- Use <defs> with <symbol id="..."> for reusable graphics (card suits, icons)
- Reference symbols with <use href="#symbol-id" x="..." y="...">
- Use <g id="..." transform="..."> for logical groups
- Card suit colors: spades/clubs #1a1a2e (dark), hearts/diamonds #e63946 (red)
- Playing card: rect rx="8" fill="white" stroke="#ccc" stroke-width="1"
- FORBIDDEN: inline JavaScript, external image references, non-SVG elements
- Output ONLY the SVG content starting with <svg. No explanations. No markdown fences."""

_SYSTEM_NODE_TS = """# ROLE
Node.js/TypeScript backend developer. Write idiomatic server-side TypeScript.

# RULES
- ESM imports only (import ... from '...'  or import type ...); no require()
- Declare types for ALL function parameters and return values; avoid any
- async/await everywhere for I/O; never mix callbacks and promises
- Named exports preferred over default exports
- FORBIDDEN: any type (use unknown + narrowing), empty catch, TODO stubs, console.log in production
- Output ONLY the TypeScript file content. No explanations. No markdown fences."""

_SYSTEM_PHP = """# ROLE
Expert PHP developer. Write clean, modern PHP 8.x code.

# RULES
- Start with <?php declare(strict_types=1);
- Use namespaces and PSR-4 autoloading conventions
- Type hints on all function parameters and return types
- Use match expressions over switch; null coalescing ??, named arguments
- FORBIDDEN: mysql_* functions (use PDO/MySQLi), global variables, eval(), TODO stubs
- Output ONLY the PHP file content. No explanations. No markdown fences."""

_SYSTEM_RUBY = """# ROLE
Expert Ruby developer. Write clean, idiomatic Ruby code.

# RULES
- Use snake_case for methods and variables; CamelCase for classes/modules
- Prefer blocks, iterators, and Enumerable methods over loops
- Use attr_accessor/reader/writer; avoid instance variable access outside the class
- Raise specific exception classes; rescue specific exceptions (not bare rescue)
- FORBIDDEN: global variables ($x), method_missing without respond_to_missing?, TODO stubs
- Output ONLY the Ruby file content. No explanations. No markdown fences."""

_SYSTEM_KOTLIN = """# ROLE
Expert Kotlin developer. Write clean, idiomatic Kotlin code.

# RULES
- Use data class for DTOs; sealed class for exhaustive type hierarchies
- Prefer val over var; use nullable types T? only when null is meaningful
- Use when expressions exhaustively; extension functions for utility methods
- Coroutines for async: suspend fun, launch, async, Flow for streams
- FORBIDDEN: !! (null assertion), Java-style for loops, TODO() without implementation
- Output ONLY the Kotlin file content. No explanations. No markdown fences."""

_SYSTEM_DART = """# ROLE
Expert Dart/Flutter developer. Write clean, idiomatic Dart code.

# RULES
- Use null safety: declare types as T? only when null is possible, use ! only after null check
- Prefer final over var; use const constructors where possible
- Flutter widgets: StatelessWidget for pure UI, StatefulWidget for mutable state
- Use async/await with Future<T>; avoid .then() chaining
- FORBIDDEN: dynamic type (use Object?), print() in production (use debugPrint), TODO stubs
- Output ONLY the Dart file content. No explanations. No markdown fences."""

# Map file extensions to their specialized system prompts (for non-small models)
_SYSTEM_BY_EXT: dict[str, str] = {
    ".go": _SYSTEM_GO,
    ".rs": _SYSTEM_RUST,
    ".java": _SYSTEM_JAVA,
    ".cs": _SYSTEM_CSHARP,
    ".svg": _SYSTEM_SVG,
    ".php": _SYSTEM_PHP,
    ".rb": _SYSTEM_RUBY,
    ".kt": _SYSTEM_KOTLIN,
    ".kts": _SYSTEM_KOTLIN,
    ".dart": _SYSTEM_DART,
}

# Compact versions for small models (≤8B)
_SYSTEM_BY_EXT_SMALL: dict[str, str] = {
    ".go": "Go developer. Write idiomatic Go: package decl, all imports used, if err!=nil{return err}, CamelCase exported. Output code only.",
    ".rs": "Rust developer. Write safe Rust: use statements, Result<T,E> with ?, no unwrap() in prod. Output code only.",
    ".java": "Java developer. Write clean Java: package+imports, public class matches filename, checked exceptions handled. Output code only.",
    ".cs": "C# developer. Write idiomatic C#: namespaces+usings, PascalCase methods, async/await for I/O. Output code only.",
    ".svg": "SVG designer. Write SVG with xmlns, viewBox, <defs>/<symbol> for card suits, <use> for references. Output SVG only.",
    ".php": "PHP developer. Write PHP 8 with <?php declare(strict_types=1); namespaces, type hints, PDO for DB. Output code only.",
    ".rb": "Ruby developer. Write idiomatic Ruby: snake_case, iterators, attr_accessor, rescue specific exceptions. Output code only.",
    ".kt": "Kotlin developer. Write idiomatic Kotlin: data class, val>var, when expressions, coroutines for async. Output code only.",
    ".dart": "Dart developer. Write null-safe Dart: final>var, const constructors, async/await, StatelessWidget or StatefulWidget. Output code only.",
}

_USER_FULL = """## PROJECT CONTEXT
Name: {project_name}
Description: {project_description}

## FILE TO GENERATE
Path: {file_path}
Purpose: {purpose}
Public exports: {exports}
Depends on files: {imports}
Key implementation: {key_logic}

## DEPENDENCY SIGNATURES (from already-generated files)
{signature_context}

## PREVIOUSLY GENERATED
{previous_summary}

Write the complete content of `{file_path}` now:"""

_USER_SMALL = """Project: {project_name} — {project_description}
File: {file_path}
Purpose: {purpose}
Depends on: {imports}
Key logic: {key_logic}

{signature_context}

Write {file_path}:"""

_CONFIG_SYSTEM = "Generate the content of the requested config/doc file. Output only the file content."

_CONFIG_USER = """File: {file_path}
Purpose: {purpose}
Project type: {project_type}
Tech stack: {tech_stack}
Key logic / content: {key_logic}

Write {file_path}:"""

# Max workers for parallel independent-file generation (#7)
_PARALLEL_WORKERS = 2


class CodeFillPhase(BasePhase):
    phase_id = "4"
    phase_label = "Code Fill"

    def run(self, ctx: PhaseContext) -> None:
        is_small = ctx.is_small()

        # #8 — Blueprint-hash cache: skip generation if identical project exists
        if self._cache_hit(ctx):
            ctx.logger.info("[CodeFill] Cache hit — restoring from previous generation")
            self._restore_from_cache(ctx)
            return

        system_tmpl = _SYSTEM_SMALL if is_small else _SYSTEM_FULL
        user_tmpl = _USER_SMALL if is_small else _USER_FULL

        generated_count = 0
        failure_count = 0

        # Group files by priority for parallel execution (#7)
        # Files in the same priority group have no inter-dependencies.
        priority_groups = self._group_by_priority(ctx.blueprint)

        # Shared coherence accumulator (thread-safe via lock)
        lock = threading.Lock()

        for group in priority_groups:
            non_code = [p for p in group if self._is_non_code(p.path)]
            code_files = [p for p in group if not self._is_non_code(p.path)]

            # Non-code files are fast — generate sequentially
            for plan in non_code:
                self._generate_config(ctx, plan, no_think=is_small)
                generated_count += 1

            if not code_files:
                continue

            # Single file in group — no parallelism overhead
            if len(code_files) == 1:
                ok = self._fill_one(ctx, code_files[0], system_tmpl, user_tmpl, is_small, lock)
                if ok:
                    generated_count += 1
                else:
                    failure_count += 1
            else:
                # Multiple independent files → parallel (#7)
                with concurrent.futures.ThreadPoolExecutor(max_workers=_PARALLEL_WORKERS) as pool:
                    futures = {
                        pool.submit(self._fill_one, ctx, plan, system_tmpl, user_tmpl, is_small, lock): plan
                        for plan in code_files
                    }
                    for future in concurrent.futures.as_completed(futures):
                        if future.result():
                            generated_count += 1
                        else:
                            failure_count += 1

        ctx.metrics["code_fill_generated"] = generated_count
        ctx.metrics["code_fill_failures"] = failure_count
        ctx.logger.info(f"[CodeFill] {generated_count} files generated, {failure_count} failures")

        # #2 — Coherence validation: verify declared exports exist in generated files
        coherence_warnings = self._validate_coherence(ctx)
        if coherence_warnings:
            ctx.metrics["coherence_warnings"] = coherence_warnings
            for w in coherence_warnings:
                ctx.logger.warning(f"[CodeFill] Coherence: {w}")

        # #8 — Save cache after successful generation
        self._save_cache(ctx)

    # ----------------------------------------------------------------
    # Per-file generation (called from both sequential and parallel paths)
    # ----------------------------------------------------------------

    def _fill_one(
        self,
        ctx: PhaseContext,
        plan: FilePlan,
        system_tmpl: str,
        user_tmpl: str,
        is_small: bool,
        lock: threading.Lock,
    ) -> bool:
        """Generate a single code file. Thread-safe. Returns True on success."""
        language = self._detect_language(plan.path)
        sig_context = self._build_signature_context(ctx, plan)

        ext = Path(plan.path).suffix.lower()
        if ext == ".html":
            system = _SYSTEM_HTML
        elif ext in (".css", ".scss"):
            system = _SYSTEM_CSS
        elif self._is_browser_js(ctx, plan.path):
            system = _SYSTEM_BROWSER_JS_SMALL if is_small else _SYSTEM_BROWSER_JS
        elif ext in (_SYSTEM_BY_EXT_SMALL if is_small else _SYSTEM_BY_EXT):
            system = (_SYSTEM_BY_EXT_SMALL if is_small else _SYSTEM_BY_EXT)[ext]
        else:
            system = system_tmpl.format(language=language)

        if is_small:
            user = user_tmpl.format(
                project_name=ctx.project_name,
                project_description=ctx.project_description[:200],
                file_path=plan.path,
                purpose=plan.purpose,
                imports=", ".join(plan.imports) or "none",
                key_logic=plan.key_logic or "implement as described",
                signature_context=sig_context,
            )
        else:
            # Use a thread-local copy of previous_summary to avoid races.
            # In parallel groups, previous_summary is "" for all files in the group.
            user = user_tmpl.format(
                project_name=ctx.project_name,
                project_description=ctx.project_description[:400],
                file_path=plan.path,
                purpose=plan.purpose,
                exports=", ".join(plan.exports) or "none",
                imports=", ".join(plan.imports) or "none",
                key_logic=plan.key_logic or "implement as described",
                signature_context=sig_context,
                previous_summary="",
            )
            if self._is_browser_js(ctx, plan.path):
                dom_contract = self._build_dom_contract(ctx)
                if dom_contract:
                    user += f"\n\n## DOM CONTRACT (IDs/classes already defined in HTML/CSS)\n{dom_contract}"

            # M7 — FastAPI entry-point mandatory patterns (large models only)
            if self._is_fastapi_entry_point(ctx, plan.path):
                has_html = any(fp.path.endswith(".html") for fp in ctx.blueprint)
                has_sqlite = "sqlite" in [t.lower() for t in ctx.tech_stack]
                mandatory_block = self._build_fastapi_mandatory_block(has_html, has_sqlite)
                if mandatory_block:
                    user = user.rstrip() + f"\n\n{mandatory_block}"

            # M8 — Shared JS null guards (large models + multi-page projects)
            if self._is_shared_js(ctx, plan.path):
                user = user.rstrip() + (
                    "\n\n## MULTI-PAGE GUARD — MANDATORY:\n"
                    "This JS runs on MULTIPLE pages with DIFFERENT DOM elements.\n"
                    "RULE: Always null-check before any DOM access:\n"
                    "  const el = document.getElementById('x'); if (!el) return;\n"
                    "Apply this guard to EVERY getElementById / querySelector call."
                )

        num_predict = self._estimate_num_predict(plan)
        content = self._generate_with_retry(ctx, system, user, plan, no_think=is_small, max_tokens=num_predict)

        if content:
            with lock:
                self._write_file(ctx, plan.path, content)
            ctx.logger.info(f"  [CodeFill] {plan.path} ({len(content)} chars)")
            # #13 — SSE event per file
            ctx.event_publisher.publish_sync(
                "file_generated",
                path=plan.path,
                chars=len(content),
                phase="code_fill",
            )
            return True
        else:
            ctx.errors.append(f"CodeFill: failed to generate {plan.path}")
            return False

    # ----------------------------------------------------------------
    # Generation helpers
    # ----------------------------------------------------------------

    def _generate_with_retry(
        self,
        ctx: PhaseContext,
        system: str,
        user: str,
        plan: FilePlan,
        no_think: bool = False,
        max_tokens: int = 2048,
    ) -> Optional[str]:
        """Try to generate file content. One retry on syntax error.

        #4 — Smart retry: the retry prompt includes the actual syntax error message
        so the model knows exactly what to fix, not just a generic "try again".
        """
        current_user = user
        last_error: Optional[str] = None

        for attempt in range(2):
            raw = self._llm_call(ctx, system, current_user, role="coder", no_think=no_think, max_tokens=max_tokens)
            content = self._extract_code(raw, plan.path)

            syntax_ok, syntax_error = self._validate_syntax_detailed(plan.path, content)
            if content and syntax_ok:
                return content

            last_error = syntax_error
            if attempt == 0:
                lang = self._detect_language(plan.path)
                ctx.logger.warning(f"  [CodeFill] Syntax issue in {plan.path}: {last_error or 'unknown'} — retrying")
                # #4 — Inject the exact error into the retry prompt
                error_hint = f"Error: {last_error}" if last_error else "syntax validation failed"
                current_user = (
                    user
                    + f"\n\nPREVIOUS ATTEMPT HAD A SYNTAX ERROR:\n{error_hint}\n"
                    + f"Write clean, valid {lang} code with no placeholders. Fix the issue above."
                )

        # Return best-effort content even if syntax check fails on second attempt
        raw = self._llm_call(ctx, system, current_user, role="coder", no_think=no_think, max_tokens=max_tokens)
        return self._extract_code(raw, plan.path)

    def _build_signature_context(self, ctx: PhaseContext, plan: FilePlan) -> str:
        """Return signature-only content of dependency files. Budget: ~500 tokens (~2000 chars)."""
        try:
            from backend.utils.domains.auto_generation.utilities.signature_extractor import (
                extract_signatures,
            )
        except ImportError:
            return "No signature extractor available."

        lines: List[str] = []
        chars_used = 0
        char_budget = 2000  # 500 tokens * 4 chars/token

        for dep_path in plan.imports[:3]:  # max 3 dependencies
            content = ctx.generated_files.get(dep_path, "")
            if not content:
                continue
            sigs = extract_signatures(content, dep_path)
            chunk = f"# From {dep_path}:\n{sigs}\n"
            if chars_used + len(chunk) > char_budget:
                break
            lines.append(chunk)
            chars_used += len(chunk)

        return "\n".join(lines) or "No dependency signatures available yet."

    def _generate_config(self, ctx: PhaseContext, plan: FilePlan, no_think: bool = False) -> None:
        """Generate config/doc files with a minimal dedicated prompt."""
        # Special case: README.md generated by blueprint phase already
        if plan.path == "README.md" and plan.path in ctx.generated_files:
            return

        user = _CONFIG_USER.format(
            file_path=plan.path,
            purpose=plan.purpose,
            project_type=ctx.project_type,
            tech_stack=", ".join(ctx.tech_stack),
            key_logic=plan.key_logic or "standard content for this file type",
        )
        content = self._llm_call(ctx, _CONFIG_SYSTEM, user, role="coder", no_think=no_think)
        if content:
            self._write_file(ctx, plan.path, content.strip())
            # #13 — SSE for config files too
            ctx.event_publisher.publish_sync(
                "file_generated",
                path=plan.path,
                chars=len(content),
                phase="code_fill",
            )

    # ----------------------------------------------------------------
    # #2 — Coherence validation
    # ----------------------------------------------------------------

    def _validate_coherence(self, ctx: PhaseContext) -> List[str]:
        """Check that declared exports actually appear in generated files.

        Zero-LLM. Uses simple name search (not AST) for speed and multi-language
        compatibility. Reports missing exports as warnings (not errors).
        """
        warnings: List[str] = []
        for plan in ctx.blueprint:
            if not plan.exports:
                continue
            content = ctx.generated_files.get(plan.path, "")
            if not content:
                continue
            for export_name in plan.exports:
                # Simple presence check — the name should appear somewhere in the file
                if export_name and export_name not in content:
                    warnings.append(f"{plan.path}: declared export '{export_name}' not found in generated content")
        return warnings

    # ----------------------------------------------------------------
    # #7 — Priority grouping for parallel execution
    # ----------------------------------------------------------------

    @staticmethod
    def _group_by_priority(blueprint: List[FilePlan]) -> List[List[FilePlan]]:
        """Group files by priority level. Files in the same group are independent."""
        from itertools import groupby

        sorted_plans = sorted(blueprint, key=lambda fp: fp.priority)
        groups: List[List[FilePlan]] = []
        for _, g in groupby(sorted_plans, key=lambda fp: fp.priority):
            groups.append(list(g))
        return groups

    # ----------------------------------------------------------------
    # #8 — Blueprint-hash cache
    # ----------------------------------------------------------------

    def _blueprint_hash(self, ctx: PhaseContext) -> str:
        """SHA-256 of project_description + blueprint JSON (deterministic)."""
        import dataclasses

        payload = json.dumps(
            {
                "desc": ctx.project_description,
                "blueprint": [dataclasses.asdict(fp) for fp in ctx.blueprint],
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def _cache_dir(self, ctx: PhaseContext) -> Path:
        return ctx.project_root / ".ollash" / "gen_cache"

    def _cache_hit(self, ctx: PhaseContext) -> bool:
        """True if a cache entry matching the current blueprint hash exists."""
        bhash = self._blueprint_hash(ctx)
        marker = self._cache_dir(ctx) / f"{bhash}.json"
        return marker.exists()

    def _restore_from_cache(self, ctx: PhaseContext) -> None:
        """Load generated file paths from cache and re-read their content from disk."""
        bhash = self._blueprint_hash(ctx)
        marker = self._cache_dir(ctx) / f"{bhash}.json"
        try:
            paths = json.loads(marker.read_text(encoding="utf-8"))
            for rel_path in paths:
                abs_path = ctx.project_root / rel_path
                if abs_path.exists():
                    ctx.generated_files[rel_path] = abs_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, json.JSONDecodeError) as e:
            ctx.logger.warning(f"[CodeFill] Cache restore failed: {e}")

    def _save_cache(self, ctx: PhaseContext) -> None:
        """Write cache marker file with list of generated file paths."""
        bhash = self._blueprint_hash(ctx)
        cache_dir = self._cache_dir(ctx)
        cache_dir.mkdir(parents=True, exist_ok=True)
        marker = cache_dir / f"{bhash}.json"
        try:
            marker.write_text(
                json.dumps(list(ctx.generated_files.keys()), indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            ctx.logger.warning(f"[CodeFill] Cache save failed: {e}")

    # ----------------------------------------------------------------
    # C5 — Dynamic num_predict based on file complexity
    # ----------------------------------------------------------------

    @staticmethod
    def _estimate_num_predict(plan: FilePlan) -> int:
        """Return 4096 tokens for files with complex domain logic, 2048 otherwise.

        Detects complexity from the file path and key_logic hint. Game engines,
        hand evaluators, parsers, and compilers genuinely need more output tokens.
        """
        # CSS/JS files are often large — always use 4096 to avoid truncation
        if plan.path.endswith((".css", ".js", ".ts")):
            return 4096

        complex_hints = (
            "game",
            "logic",
            "engine",
            "core",
            "solver",
            "evaluator",
            "parser",
            "compiler",
            "renderer",
            "simulation",
            "algorithm",
            "poker",
            "chess",
            "physics",
            "ai",
            "neural",
            "crypto",
        )
        combined = (plan.path + " " + (plan.key_logic or "")).lower()
        if any(h in combined for h in complex_hints):
            return 4096
        return 2048

    # ----------------------------------------------------------------
    # Validation / extraction helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _validate_syntax_detailed(file_path: str, content: str) -> tuple[bool, Optional[str]]:
        """Syntax check for Python files. Returns (ok, error_message).

        #4 — Returns the actual SyntaxError message so it can be injected into the retry prompt.
        """
        if not content:
            return False, "empty content"
        if Path(file_path).suffix.lower() == ".py":
            try:
                ast.parse(content)
                return True, None
            except SyntaxError as e:
                return False, f"SyntaxError at line {e.lineno}: {e.msg}"
        return True, None

    @staticmethod
    def _validate_syntax(file_path: str, content: str) -> bool:
        """Legacy: syntax check — used by tests expecting the old bool return."""
        ok, _ = CodeFillPhase._validate_syntax_detailed(file_path, content)
        return ok

    @staticmethod
    def _extract_code(raw: str, file_path: str) -> str:
        """Extract code from LLM response (fenced or unfenced)."""
        try:
            from backend.utils.core.llm.llm_response_parser import LLMResponseParser

            block = LLMResponseParser.extract_code_block_for_file(raw, file_path)
            return block.strip() if block else raw.strip()
        except Exception:
            return raw.strip()

    @staticmethod
    def _is_non_code(path: str) -> bool:
        ext = Path(path).suffix.lower()
        name = Path(path).name.lower()
        return ext in _NON_CODE_EXTS or name in {"dockerfile", "makefile", "procfile"}

    @staticmethod
    def _is_browser_js(ctx: PhaseContext, path: str) -> bool:
        """True when generating a .js/.jsx file for a browser (not Node) project."""
        return Path(path).suffix.lower() in (".js", ".jsx") and ctx.project_type in (
            "frontend_web",
            "web_app",
            "game",
            "python_app",
            "api",
        )

    @staticmethod
    def _is_fastapi_entry_point(ctx: PhaseContext, path: str) -> bool:
        """True for main Python entry files in a FastAPI project (M7)."""
        return Path(path).name.lower() in {"app.py", "main.py", "server.py", "run.py"} and "fastapi" in [
            t.lower() for t in ctx.tech_stack
        ]

    @staticmethod
    def _build_fastapi_mandatory_block(has_html: bool, has_sqlite: bool) -> str:
        """Return a MANDATORY PATTERNS block for FastAPI entry points (M7)."""
        lines = ["## MANDATORY PATTERNS — include ALL of these:"]
        if has_html:
            lines.append("- app.mount('/static', StaticFiles(directory='static'), name='static')")
            lines.append("- from fastapi.staticfiles import StaticFiles  # required import")
        if has_sqlite:
            lines.append("- @app.on_event('startup') async def startup(): init_db()  # NOT only in __main__")
            lines.append("- Use 'with sqlite3.connect(DB) as conn:' context manager — NEVER call conn.close() manually")
        lines.append("- GET /api/<resource> endpoint that returns ALL records as a list (not only by ID)")
        lines.append("- All API endpoints must be tested with curl or UI before ship")
        return "\n".join(lines)

    @staticmethod
    def _is_shared_js(ctx: PhaseContext, path: str) -> bool:
        """True when a JS file is imported by 2+ HTML files in the blueprint (M8)."""
        if Path(path).suffix.lower() not in (".js", ".jsx"):
            return False
        js_name = Path(path).name
        html_importers = sum(
            1 for fp in ctx.blueprint if fp.path.endswith(".html") and (path in fp.imports or js_name in fp.imports)
        )
        return html_importers > 1

    @staticmethod
    def _build_dom_contract(ctx: PhaseContext) -> str:
        """Extract element IDs and CSS class names for JS coherence.

        #6 — Sources (in priority order):
        1. Already-generated HTML/CSS files (most accurate)
        2. Blueprint key_logic for HTML/CSS files not yet generated (forward-looking)
        3. Blueprint key_logic for JS files — extracts referenced DOM element hints
        """
        lines: List[str] = []

        # Source 1: already-generated files
        for path, content in ctx.generated_files.items():
            ext = Path(path).suffix.lower()
            if ext == ".html":
                ids = re.findall(r'\bid=["\']([^"\']+)["\']', content)
                classes_raw = re.findall(r'\bclass=["\']([^"\']+)["\']', content)
                flat_classes = [c for cls in classes_raw for c in cls.split()]
                if ids:
                    lines.append(f"HTML IDs: {', '.join(f'#{i}' for i in ids[:8])}")
                if flat_classes:
                    lines.append(f"HTML classes: {', '.join(f'.{c}' for c in flat_classes[:8])}")
            elif ext in (".css", ".scss"):
                selectors = re.findall(r"\.([\w-]+)\s*\{", content)
                if selectors:
                    lines.append(f"CSS classes in {path}: {', '.join(f'.{s}' for s in selectors[:8])}")

        # Source 2 & 3: blueprint key_logic for ungenerated files
        if ctx.blueprint:
            for fp in ctx.blueprint:
                if fp.path in ctx.generated_files or not fp.key_logic:
                    continue
                ext = Path(fp.path).suffix.lower()
                if ext == ".html":
                    ids = re.findall(r"id=([#\w-]+)", fp.key_logic)
                    classes = re.findall(r"class=([.\w-]+)", fp.key_logic)
                    if ids:
                        clean_ids = [i.lstrip("#") for i in ids[:8]]
                        lines.append(f"Planned HTML IDs: {', '.join(f'#{i}' for i in clean_ids)}")
                    if classes:
                        clean_cls = [c.lstrip(".") for c in classes[:8]]
                        lines.append(f"Planned HTML classes: {', '.join(f'.{c}' for c in clean_cls)}")
                elif ext in (".css", ".scss"):
                    classes = re.findall(r"\.([\w-]+)", fp.key_logic)
                    if classes:
                        lines.append(f"Planned CSS classes: {', '.join(f'.{c}' for c in classes[:8])}")
                elif ext in (".js", ".jsx"):
                    # #6 — Extract DOM references from JS key_logic too
                    js_ids = re.findall(r"#([\w-]+)", fp.key_logic)
                    js_cls = re.findall(r"\.([\w-]+)", fp.key_logic)
                    if js_ids:
                        lines.append(f"JS references IDs: {', '.join(f'#{i}' for i in js_ids[:6])}")
                    if js_cls:
                        lines.append(f"JS references classes: {', '.join(f'.{c}' for c in js_cls[:6])}")

        return "\n".join(lines)

    @staticmethod
    def _detect_language(path: str) -> str:
        ext_map = {
            ".py": "Python",
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".js": "JavaScript",
            ".jsx": "JavaScript",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".cs": "C#",
            ".cpp": "C++",
            ".html": "HTML",
            ".css": "CSS",
            ".scss": "SCSS",
            ".svg": "SVG",
        }
        try:
            from backend.utils.core.language_utils import LanguageUtils

            lang = LanguageUtils.infer_language(path)
            if lang != "unknown":
                return lang.capitalize()
        except Exception:
            pass
        return ext_map.get(Path(path).suffix.lower(), "Python")
