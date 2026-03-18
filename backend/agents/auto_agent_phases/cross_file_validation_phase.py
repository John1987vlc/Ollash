"""Phase 4b: CrossFileValidationPhase — zero-LLM contract validation between files.

Runs after CodeFillPhase, before PatchPhase. Catches the most damaging class of
errors that static analysis misses: semantic mismatches between files that are each
individually valid but incompatible when combined.

Three validation passes:
  1. HTML ↔ JS ID contract   — getElementById/querySelector refs vs actual HTML ids
  2. HTML ↔ CSS class contract — HTML class attributes vs CSS selector definitions
  3. Python relative imports   — imported names vs exported symbols in target module

Auto-fix strategy (ID mismatches only):
  If JS looks for an ID and HTML has a similarly-named id (SequenceMatcher > 0.5),
  update the HTML id to match — JS is treated as the "spec" since it encodes intent.
  Unfixable errors go into ctx.cross_file_errors for PatchPhase to consume.

This phase is included in BOTH FULL_PHASE_ORDER and SMALL_PHASE_ORDER because it
costs zero LLM tokens — pure regex + difflib.
"""

from __future__ import annotations

import ast
import difflib
import re
from typing import Any, Dict, List, Set, Tuple

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


class CrossFileValidationPhase(BasePhase):
    phase_id = "4b"
    phase_label = "Cross-File Validation"

    def run(self, ctx: PhaseContext) -> None:
        if not ctx.generated_files:
            ctx.logger.info("[CrossFileValidation] No generated files — skipping")
            return

        try:
            self._run_validation(ctx)
        except Exception as e:
            ctx.logger.warning(f"[CrossFileValidation] Unexpected error (non-fatal): {e}")

    # ----------------------------------------------------------------
    # Main validation orchestrator
    # ----------------------------------------------------------------

    def _run_validation(self, ctx: PhaseContext) -> None:
        all_errors: List[Dict[str, Any]] = []

        has_html = any(p.endswith(".html") for p in ctx.generated_files)
        has_js = any(p.endswith(".js") for p in ctx.generated_files)
        has_css = any(p.endswith(".css") for p in ctx.generated_files)
        has_py = any(p.endswith(".py") for p in ctx.generated_files)

        if has_html and has_js:
            all_errors.extend(self._check_html_js_ids(ctx))
        if has_html and has_css:
            all_errors.extend(self._check_html_css_classes(ctx))
        if has_py:
            all_errors.extend(self._check_python_imports(ctx))
        # Pass 7: Python constructor arity — catch VaultCrypto(x) vs __init__(self, x, y)
        if has_py:
            all_errors.extend(self._check_python_constructor_arity(ctx))
        # M5 — Pass 4: JS fetch() URLs vs backend API routes (zero-LLM)
        if has_js and has_py:
            all_errors.extend(self._check_js_fetch_vs_routes(ctx))
        # M6 — Pass 5: HTML form field names vs Pydantic model fields (zero-LLM)
        if has_html and has_py:
            all_errors.extend(self._check_form_fields_vs_models(ctx))
        # Bug 3 — Pass 6: Duplicate window.* exports across JS files (advisory)
        js_count = sum(1 for p in ctx.generated_files if p.endswith(".js"))
        if has_js and js_count >= 2:
            all_errors.extend(self._check_duplicate_window_exports(ctx))

        # Pass 8: C# class/interface reference consistency (zero-LLM)
        has_cs = any(p.endswith(".cs") for p in ctx.generated_files)
        if has_cs:
            all_errors.extend(self._check_csharp_class_references(ctx))

        # I6 — Pass 9: DB-seeded string case vs frontend string case (zero-LLM)
        if has_py and (has_js or has_html):
            all_errors.extend(self._check_case_sensitive_constants(ctx))

        # M7 — Zero-LLM auto-fix: broken HTML asset paths (e.g. style.css → static/style.css)
        if has_html:
            self._fix_broken_html_asset_paths(ctx)

        # Attempt zero-LLM auto-fixes for ID mismatches
        auto_fixed = self._attempt_auto_fixes(ctx, all_errors)
        auto_fixed_set = {id(e) for e in auto_fixed}

        # Remaining errors go to ctx.cross_file_errors for PatchPhase
        for err in all_errors:
            if id(err) not in auto_fixed_set:
                # Strip internal tracking keys before storing
                clean = {k: v for k, v in err.items() if not k.startswith("_")}
                ctx.cross_file_errors.append(clean)

        ctx.metrics["cross_file_errors_found"] = len(all_errors)
        ctx.metrics["cross_file_errors_auto_fixed"] = len(auto_fixed)

        if all_errors:
            ctx.logger.info(
                f"[CrossFileValidation] {len(all_errors)} errors found, "
                f"{len(auto_fixed)} auto-fixed, "
                f"{len(ctx.cross_file_errors)} passed to PatchPhase"
            )
        else:
            ctx.logger.info("[CrossFileValidation] No cross-file contract errors found")

    # ----------------------------------------------------------------
    # Pass 1: HTML ↔ JS ID contract
    # ----------------------------------------------------------------

    def _check_html_js_ids(self, ctx: PhaseContext) -> List[Dict[str, Any]]:
        """Detect getElementById / querySelector('#id') calls whose targets don't exist in HTML."""
        html_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".html")}
        js_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".js")}

        # Collect all HTML ids across all HTML files
        html_ids: Set[str] = set()
        primary_html = ""
        for path, content in html_files.items():
            ids = re.findall(r'id=["\']([^"\']+)["\']', content)
            html_ids.update(ids)
            if not primary_html:
                primary_html = path

        errors: List[Dict[str, Any]] = []
        for js_path, js_content in js_files.items():
            # getElementsById("id") and getElementById('id')
            gebi = set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", js_content))
            # querySelector("#id") and querySelector('#id')
            qs_hash = set(re.findall(r'querySelector\s*\(\s*[\'"]#([^\'\"#)]+)[\'"]', js_content))
            # querySelectorAll("#id")
            qsa_hash = set(re.findall(r'querySelectorAll\s*\(\s*[\'"]#([^\'\"#)]+)[\'"]', js_content))

            missing = (gebi | qs_hash | qsa_hash) - html_ids
            for ref_id in sorted(missing):
                errors.append(
                    {
                        "file_a": js_path,
                        "file_b": primary_html,
                        "error_type": "id_mismatch",
                        "description": (
                            f"JS references '#{ref_id}' but no HTML element has that id. "
                            f"Known HTML ids: {sorted(html_ids)[:8]}"
                        ),
                        "suggestion": f"Add id='{ref_id}' to the correct HTML element, or update JS",
                        # Internal tracking keys (stripped before storing in cross_file_errors)
                        "_js_ref": ref_id,
                        "_html_ids": html_ids,
                        "_html_content_key": primary_html,
                    }
                )
        return errors

    # ----------------------------------------------------------------
    # Pass 2: HTML ↔ CSS class contract (advisory)
    # ----------------------------------------------------------------

    def _check_html_css_classes(self, ctx: PhaseContext) -> List[Dict[str, Any]]:
        """Detect HTML class names that have no corresponding CSS selector.

        This is advisory only (classes may be intentionally unstyled, e.g. JS hooks).
        Reported errors go to cross_file_errors but are lower priority than ID mismatches.
        """
        html_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".html")}
        css_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".css")}

        html_classes: Set[str] = set()
        for content in html_files.values():
            for match in re.findall(r'class=["\']([^"\']+)["\']', content):
                html_classes.update(match.split())

        css_selectors: Set[str] = set()
        for content in css_files.values():
            css_selectors.update(re.findall(r"\.([\w-]+)\s*[{,]", content))

        # Filter out common utility/framework classes that are typically not defined
        # in the generated CSS (e.g. Bootstrap, Tailwind)
        ignored_prefixes = (
            "btn",
            "col-",
            "row",
            "container",
            "d-",
            "flex",
            "grid",
            "text-",
            "bg-",
            "mt-",
            "mb-",
            "p-",
            "m-",
            "w-",
            "h-",
            "justify",
            "align",
            "hidden",
            "block",
            "inline",
            "fixed",
            "absolute",
            "relative",
        )
        missing_css = {
            cls for cls in html_classes - css_selectors if not any(cls.startswith(p) for p in ignored_prefixes)
        }

        errors: List[Dict[str, Any]] = []
        primary_css = next(iter(css_files.keys()), "")
        primary_html = next(iter(html_files.keys()), "")

        for cls in sorted(missing_css)[:10]:  # cap to avoid noise
            errors.append(
                {
                    "file_a": primary_html,
                    "file_b": primary_css,
                    "error_type": "missing_css_class",
                    "description": f"HTML uses class='{cls}' but no CSS rule defines .{cls}",
                    "suggestion": f"Add a .{cls} rule to {primary_css}",
                }
            )
        return errors

    # ----------------------------------------------------------------
    # Pass 3: Python relative import check
    # ----------------------------------------------------------------

    def _check_python_imports(self, ctx: PhaseContext) -> List[Dict[str, Any]]:
        """Check that relative imports resolve to names that exist in the target module."""
        py_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".py")}
        errors: List[Dict[str, Any]] = []

        for py_path, content in py_files.items():
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue  # Syntax errors handled by PatchPhase

            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.level:
                    continue  # only relative imports (level > 0)

                target_rel = self._resolve_relative_import(py_path, node.module or "", node.level)
                if target_rel not in py_files:
                    continue  # target not in generated files — skip (may be stdlib/installed)

                target_content = py_files[target_rel]
                for alias in node.names:
                    name = alias.name
                    if name == "*":
                        continue
                    if not self._name_defined_in(name, target_content):
                        errors.append(
                            {
                                "file_a": py_path,
                                "file_b": target_rel,
                                "error_type": "missing_import_name",
                                "description": (
                                    f"'{py_path}' imports '{name}' from '{target_rel}' "
                                    "but that name is not defined there"
                                ),
                                "suggestion": f"Add '{name}' to '{target_rel}' or fix the import",
                            }
                        )

        return errors

    @staticmethod
    def _resolve_relative_import(importer: str, module: str, level: int) -> str:
        """Convert a relative import to a project-relative file path.

        e.g. importer="src/utils/helper.py", module="models", level=1
             → "src/utils/models.py"
        """
        parts = importer.replace("\\", "/").split("/")
        # Go up `level` directories from the file's directory
        base_parts = parts[: max(0, len(parts) - level)]
        if module:
            base_parts += module.split(".")
        return "/".join(base_parts) + ".py"

    @staticmethod
    def _name_defined_in(name: str, content: str) -> bool:
        """Check whether `name` is exported/defined in `content` (best-effort)."""
        patterns = [
            rf"^def {re.escape(name)}\b",
            rf"^class {re.escape(name)}\b",
            rf"^{re.escape(name)}\s*=",
            rf"^{re.escape(name)}:",  # TypedDict etc.
        ]
        for pattern in patterns:
            if re.search(pattern, content, re.MULTILINE):
                return True
        return False

    # ----------------------------------------------------------------
    # Auto-fix: ID mismatches (zero-LLM)
    # ----------------------------------------------------------------

    def _attempt_auto_fixes(self, ctx: PhaseContext, errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Try to auto-fix id_mismatch errors by updating the HTML id to match JS.

        Only auto-fixes when there is exactly one HTML file (avoid ambiguity) and when
        the SequenceMatcher similarity ratio between the JS ref and nearest HTML id > 0.5.

        Returns the list of errors that were successfully fixed.
        """
        id_errors = [e for e in errors if e.get("error_type") == "id_mismatch"]
        if not id_errors:
            return []

        # Only auto-fix when there's exactly one HTML file to avoid ambiguity
        html_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".html")}
        if len(html_files) != 1:
            return []

        html_path, html_content = next(iter(html_files.items()))
        fixed: List[Dict[str, Any]] = []
        # Bug 3 fix: track source IDs already renamed this pass to prevent cascade renames
        already_renamed_from: Set[str] = set()

        for err in id_errors:
            missing_id: str = err.get("_js_ref", "")
            html_ids: Set[str] = err.get("_html_ids", set())

            if not missing_id or not html_ids:
                continue

            # Find the best matching existing HTML id
            best_match, ratio = self._best_match(missing_id, html_ids)
            if ratio <= 0.5:
                ctx.logger.info(
                    f"[CrossFileValidation] ID '{missing_id}' has no similar HTML id "
                    f"(best: '{best_match}', ratio={ratio:.2f}) — deferring to PatchPhase"
                )
                continue

            # Bug 3 fix: skip if this source id was already renamed in this pass
            if best_match in already_renamed_from:
                ctx.logger.info(
                    f"[CrossFileValidation] Skipping cascade: '{best_match}' already renamed "
                    f"this pass (would create '{missing_id}') — deferring to PatchPhase"
                )
                continue

            # Apply the fix: replace id="best_match" → id="missing_id" (first occurrence)
            old_attr = f'id="{best_match}"'
            new_attr = f'id="{missing_id}"'
            if old_attr not in html_content:
                # Try single quotes
                old_attr = f"id='{best_match}'"
                new_attr = f"id='{missing_id}'"

            if old_attr in html_content:
                new_html = html_content.replace(old_attr, new_attr, 1)
                self._write_file(ctx, html_path, new_html)
                # Update local html_content for subsequent fixes in same file
                html_content = new_html
                # Also update the set for next error in loop
                if isinstance(html_ids, set):
                    html_ids.discard(best_match)
                    html_ids.add(missing_id)
                already_renamed_from.add(best_match)
                ctx.logger.info(
                    f"[CrossFileValidation] Auto-fixed: id='{best_match}' → id='{missing_id}' "
                    f"in {html_path} (ratio={ratio:.2f})"
                )
                fixed.append(err)

        return fixed

    @staticmethod
    def _best_match(target: str, candidates: Set[str]) -> Tuple[str, float]:
        """Return (best_candidate, similarity_ratio) from candidates."""
        best = ""
        best_ratio = 0.0
        for cand in candidates:
            ratio = difflib.SequenceMatcher(None, target, cand).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best = cand
        return best, best_ratio

    # ----------------------------------------------------------------
    # Bug 3 — Pass 6: Duplicate window.* exports across JS files
    # ----------------------------------------------------------------

    def _check_duplicate_window_exports(self, ctx: PhaseContext) -> List[Dict[str, Any]]:
        """Detect multiple JS files assigning the same name on window.*.

        e.g. both game.js and board.js define window.renderBoard — signals a blueprint
        file-split problem where both files independently implemented the same logic.
        Advisory only: not auto-fixable, passed to PatchPhase to consolidate.
        """
        _WINDOW_ASSIGN_RE = re.compile(
            r"window\.(\w+)\s*=\s*(?:function|\w)",
            re.MULTILINE,
        )
        js_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".js")}

        window_exports: Dict[str, List[str]] = {}
        for js_path, content in js_files.items():
            for m in _WINDOW_ASSIGN_RE.finditer(content):
                name = m.group(1)
                window_exports.setdefault(name, []).append(js_path)

        errors: List[Dict[str, Any]] = []
        for name, files in window_exports.items():
            if len(files) < 2:
                continue
            errors.append(
                {
                    "file_a": files[0],
                    "file_b": files[1],
                    "error_type": "duplicate_global_export",
                    "description": (
                        f"Both {files[0]} and {files[1]} assign window.{name} — "
                        "blueprint may have split responsibilities incorrectly"
                    ),
                    "suggestion": (f"Consolidate '{name}' into one JS file, or rename to avoid collision"),
                }
            )
        return errors

    # ----------------------------------------------------------------
    # Pass 8: C# class/interface reference consistency
    # ----------------------------------------------------------------

    def _check_csharp_class_references(self, ctx: PhaseContext) -> List[Dict[str, Any]]:
        """Detect C# constructor calls / field types that reference undefined project-local names.

        Scope: only PascalCase names defined and used within the generated .cs files.
        Known .NET BCL / ASP.NET types are excluded to avoid false positives.
        """
        cs_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".cs")}
        if not cs_files:
            return []

        # Step 1 — collect all types defined in the project
        _DEFN_RE = re.compile(r"\bpublic\s+(?:class|interface|record|struct|enum)\s+(\w+)")
        defined_names: set[str] = set()
        for content in cs_files.values():
            defined_names.update(_DEFN_RE.findall(content))

        if not defined_names:
            return []

        # Step 2 — known .NET BCL / ASP.NET / EF Core names to skip
        _KNOWN_DOTNET: set[str] = {
            "string",
            "int",
            "long",
            "float",
            "double",
            "decimal",
            "bool",
            "object",
            "byte",
            "char",
            "short",
            "uint",
            "ulong",
            "ushort",
            "sbyte",
            "List",
            "IList",
            "IEnumerable",
            "ICollection",
            "Dictionary",
            "HashSet",
            "Task",
            "ValueTask",
            "IAsyncEnumerable",
            "CancellationToken",
            "ActionResult",
            "IActionResult",
            "OkResult",
            "NotFoundResult",
            "BadRequestResult",
            "Controller",
            "ControllerBase",
            "DbContext",
            "DbSet",
            "IDbContextFactory",
            "IServiceCollection",
            "IServiceProvider",
            "IConfiguration",
            "ILogger",
            "ILoggerFactory",
            "HttpClient",
            "HttpRequest",
            "HttpResponse",
            "Exception",
            "InvalidOperationException",
            "ArgumentException",
            "ArgumentNullException",
            "NotSupportedException",
            "WebApplication",
            "WebApplicationBuilder",
            "ModelBuilder",
            "EntityTypeBuilder",
            "Nullable",
            "var",
            "dynamic",
        }

        # Step 3 — scan each file for references to project-local types
        _REF_RE = re.compile(
            r"(?:"
            r"new\s+(\w+)\s*[<(]"  # new TypeName<  or  new TypeName(
            r"|private\s+readonly\s+(\w+)\s"  # private readonly TypeName
            r"|private\s+(\w+)\s+\w+\s*[;=]"  # private TypeName fieldName;
            r"|:\s*(\w+)\s*[{,\n]"  # : BaseClass {  or  : IInterface,
            r")"
        )

        errors: List[Dict[str, Any]] = []
        seen: set[str] = set()

        for cs_path, content in cs_files.items():
            for m in _REF_RE.finditer(content):
                ref_name = next((g for g in m.groups() if g is not None), None)
                if not ref_name or not ref_name[0].isupper():
                    continue
                if ref_name in _KNOWN_DOTNET or ref_name in defined_names:
                    continue

                # Deduplicate per (file, name)
                key = (cs_path, ref_name)
                if key in seen:
                    continue
                seen.add(key)

                defined_sorted = sorted(defined_names)[:5]
                errors.append(
                    {
                        "file_a": cs_path,
                        "file_b": cs_path,
                        "error_type": "cs_undefined_type",
                        "description": (
                            f"C# file '{cs_path}' references '{ref_name}' "
                            f"which is not defined in any generated .cs file. "
                            f"Defined types: {sorted(defined_names)}"
                        ),
                        "suggestion": (f"Rename '{ref_name}' to match an existing type, e.g. {defined_sorted}"),
                    }
                )

        return errors

    # ----------------------------------------------------------------
    # M5 — Pass 4: JS fetch() URLs vs backend route decorators
    # ----------------------------------------------------------------

    def _check_js_fetch_vs_routes(self, ctx: PhaseContext) -> List[Dict[str, Any]]:
        """M5 — Detect fetch() calls in JS whose URL has no matching backend route.

        Extracts literal URLs from fetch('...') calls and compares against
        @app.get/post/put/delete/patch route decorators in Python files.
        Normalizes path parameters so /api/items/123 matches /api/items/{id}.
        Zero-LLM. Skips if no route decorators are found (non-API project guard).
        """
        _FETCH_RE = re.compile(r"fetch\s*\(\s*['\"]([^'\"$]+)['\"]", re.IGNORECASE)
        _ROUTE_RE = re.compile(
            r'@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]',
            re.IGNORECASE,
        )

        js_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".js")}
        py_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".py")}

        # Collect backend routes: normalized_path → set of HTTP methods
        backend_routes: Dict[str, set] = {}
        primary_py = ""
        for py_path, content in py_files.items():
            for method, path in _ROUTE_RE.findall(content):
                norm = self._normalize_route_path(path)
                backend_routes.setdefault(norm, set()).add(method.upper())
                if not primary_py:
                    primary_py = py_path

        # Guard: skip if no route decorators found (not a FastAPI/Flask project)
        if not backend_routes:
            return []

        errors: List[Dict[str, Any]] = []
        for js_path, js_content in js_files.items():
            for url in _FETCH_RE.findall(js_content):
                if not url.startswith("/"):
                    continue  # skip absolute URLs and external calls
                norm_url = self._normalize_route_path(url)
                if norm_url not in backend_routes:
                    known = sorted(backend_routes.keys())[:5]
                    errors.append(
                        {
                            "file_a": js_path,
                            "file_b": primary_py,
                            "error_type": "missing_api_route",
                            "description": (
                                f"JS calls fetch('{url}') but no backend route matches "
                                f"'{norm_url}'. Known routes: {known}"
                            ),
                            "suggestion": (
                                f"Add a route handler for '{url}' in {primary_py}, "
                                "or update the JS URL to match an existing route"
                            ),
                        }
                    )
        return errors

    @staticmethod
    def _normalize_route_path(path: str) -> str:
        """Normalize URL path for comparison.

        /api/bookings/123  →  /api/bookings/{param}
        /api/bookings/{booking_id}  →  /api/bookings/{param}
        """
        path = re.sub(r"/\d+", "/{param}", path)
        path = re.sub(r"/\{[^}]+\}", "/{param}", path)
        return path.rstrip("/")

    # ----------------------------------------------------------------
    # M6 — Pass 5: HTML form field names vs Pydantic model fields
    # ----------------------------------------------------------------

    def _check_form_fields_vs_models(self, ctx: PhaseContext) -> List[Dict[str, Any]]:
        """M6 — Detect HTML form input names that don't match any Pydantic model field.

        Extracts name="x" attributes from <form> elements that POST to /api/... paths,
        then checks all Pydantic BaseModel subclass fields in .py files.
        Zero-LLM.
        """
        _BASEMODEL_CLASS_RE = re.compile(r"class \w+\s*\([^)]*BaseModel[^)]*\)\s*:", re.IGNORECASE)
        _FIELD_RE = re.compile(r"^\s{4}(\w+)\s*[=:]", re.MULTILINE)
        _FORM_ACTION_RE = re.compile(r"<form[^>]+action=[\"']([^\"']*)[\"']", re.IGNORECASE)
        _INPUT_NAME_RE = re.compile(r"<input[^>]+name=[\"']([^\"']+)[\"']", re.IGNORECASE)
        _SELECT_NAME_RE = re.compile(r"<(?:select|textarea)[^>]+name=[\"']([^\"']+)[\"']", re.IGNORECASE)

        html_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".html")}
        py_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".py")}

        if not html_files or not py_files:
            return []

        # Collect all Pydantic model field names
        pydantic_fields: Set[str] = set()
        for content in py_files.values():
            for class_match in _BASEMODEL_CLASS_RE.finditer(content):
                start = class_match.end()
                class_body = content[start : start + 800]
                for field_match in _FIELD_RE.finditer(class_body):
                    name = field_match.group(1)
                    if not name.startswith("_") and name not in {"model_config", "class"}:
                        pydantic_fields.add(name)

        if not pydantic_fields:
            return []

        # Standard non-data fields to ignore
        _EXCLUDED = {"csrf_token", "submit", "_method", "action", "utf8", "authenticity_token"}

        primary_py = next(iter(py_files.keys()), "")
        errors: List[Dict[str, Any]] = []

        for html_path, html_content in html_files.items():
            # Only check forms that target /api/ endpoints
            form_actions = _FORM_ACTION_RE.findall(html_content)
            has_api_form = any("/api/" in a for a in form_actions)
            if not has_api_form:
                continue

            # Collect all input names in this file
            input_names: Set[str] = set(_INPUT_NAME_RE.findall(html_content))
            input_names.update(_SELECT_NAME_RE.findall(html_content))
            input_names -= _EXCLUDED

            for field_name in sorted(input_names):
                if field_name in pydantic_fields:
                    continue
                best, ratio = self._best_match(field_name, pydantic_fields)
                if ratio > 0.7:
                    suggestion = f"Rename form field '{field_name}' to '{best}' (similar to existing model field)"
                else:
                    suggestion = (
                        f"Add field '{field_name}' to the relevant Pydantic model in {primary_py}, "
                        "or rename the form input to match an existing field"
                    )
                errors.append(
                    {
                        "file_a": html_path,
                        "file_b": primary_py,
                        "error_type": "form_field_mismatch",
                        "description": (
                            f"HTML form has name='{field_name}' but no Pydantic model defines this field. "
                            f"Known model fields: {sorted(pydantic_fields)[:5]}"
                        ),
                        "suggestion": suggestion,
                    }
                )
        return errors

    # ----------------------------------------------------------------
    # M7 — Zero-LLM auto-fix: broken HTML asset paths
    # ----------------------------------------------------------------

    def _fix_broken_html_asset_paths(self, ctx: PhaseContext) -> None:
        """Rewrite broken <link href> / <script src> paths in HTML files.

        Detects cases where a generated HTML references an asset by a flat name
        (e.g. href="style.css") but the actual generated file lives under a
        subdirectory (e.g. "static/style.css"). Rewrites the reference directly
        in ctx.generated_files without any LLM call.
        """
        generated_paths: Set[str] = set(ctx.generated_files.keys())

        for html_path, html_content in list(ctx.generated_files.items()):
            if not html_path.endswith(".html"):
                continue

            # Find all href="..." and src="..." attribute values
            asset_refs = re.findall(r'(?:href|src)=["\']([^"\'#?]+)["\']', html_content)
            new_content = html_content

            for ref in asset_refs:
                # Skip absolute URLs and anchors
                if ref.startswith(("http://", "https://", "//", "/")):
                    continue
                # Skip if the reference already resolves correctly
                if ref in generated_paths:
                    continue
                # Look for a match under any subdirectory
                candidates = [p for p in generated_paths if p.endswith("/" + ref) or p == ref]
                if len(candidates) == 1:
                    correct_path = candidates[0]
                    new_content = new_content.replace(f'href="{ref}"', f'href="{correct_path}"')
                    new_content = new_content.replace(f"href='{ref}'", f"href='{correct_path}'")
                    new_content = new_content.replace(f'src="{ref}"', f'src="{correct_path}"')
                    new_content = new_content.replace(f"src='{ref}'", f"src='{correct_path}'")
                    ctx.logger.info(
                        f'[CrossFileValidation] M7 Auto-fixed asset path in {html_path}: "{ref}" → "{correct_path}"'
                    )

            if new_content != html_content:
                ctx.generated_files[html_path] = new_content
                # Persist the fix to disk
                try:
                    ctx.file_manager.write_file(ctx.project_root / html_path, new_content)
                except Exception as exc:
                    ctx.logger.warning(f"[CrossFileValidation] M7 Could not persist fix for {html_path}: {exc}")

    # ----------------------------------------------------------------
    # Pass 7: Python constructor arity check (zero-LLM, AST-based)
    # ----------------------------------------------------------------

    def _check_python_constructor_arity(self, ctx: PhaseContext) -> List[Dict[str, Any]]:
        """Detect call-site arity mismatches for classes defined in generated Python files.

        Example caught: VaultCrypto(password) when __init__(self, password, salt) has 2
        required params — the caller passes 1 but 2 are required.

        Only checks classes whose definitions live inside ctx.generated_files.
        Skips calls that use *args or **kwargs (arity is indeterminate).
        """
        errors: List[Dict[str, Any]] = []

        # --- Step 1: Build catalogue of class __init__ required-param counts ---
        # {ClassName: (min_required, file_path)}
        class_signatures: dict[str, tuple[int, str]] = {}

        for file_path, content in ctx.generated_files.items():
            if not file_path.endswith(".py"):
                continue
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                for item in node.body:
                    if not (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == "__init__"):
                        continue
                    args = item.args
                    # Count positional params excluding 'self'
                    total_pos = len(args.args) - 1  # subtract self
                    # Params with defaults are optional
                    n_defaults = len(args.defaults)
                    required = max(0, total_pos - n_defaults)
                    # If *args or **kwargs present, arity is open-ended — skip
                    if args.vararg or args.kwarg:
                        required = 0
                    class_signatures[node.name] = (required, file_path)

        if not class_signatures:
            return errors

        # --- Step 2: Walk all .py files looking for instantiation call sites ---
        for caller_path, content in ctx.generated_files.items():
            if not caller_path.endswith(".py"):
                continue
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue

                # Get the class name being called
                if isinstance(node.func, ast.Name):
                    cls_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    cls_name = node.func.attr
                else:
                    continue

                if cls_name not in class_signatures:
                    continue

                required, def_file = class_signatures[cls_name]
                if required == 0:
                    continue  # no required args beyond self, or open-ended

                # Count args at call site (skip starargs — arity indeterminate)
                has_starargs = any(isinstance(a, ast.Starred) for a in node.args)
                has_kwargs_unpack = any(kw.arg is None for kw in node.keywords)
                if has_starargs or has_kwargs_unpack:
                    continue

                actual = len(node.args) + len(node.keywords)
                if actual < required:
                    errors.append(
                        {
                            "type": "arity_mismatch",
                            "file": caller_path,
                            "file_b": def_file,
                            "issue": (
                                f"`{cls_name}(...)` called with {actual} positional arg(s) "
                                f"but `__init__` requires {required} (defined in {def_file})"
                            ),
                        }
                    )
                    ctx.logger.warning(
                        f"[CrossFileValidation] Pass 7 arity mismatch: "
                        f"{caller_path}: {cls_name}({actual}) — needs {required}"
                    )

        return errors

    # ----------------------------------------------------------------
    # I6 — Pass 9: DB-seeded string case vs frontend string case
    # ----------------------------------------------------------------

    def _check_case_sensitive_constants(self, ctx: PhaseContext) -> List[Dict[str, Any]]:
        """I6 — Detect string literals seeded into the DB that appear case-differently in frontend.

        Example: Python seeds 'Corte' into SQLite but HTML has <option value="corte"> — all
        lookups fail because SQLite string comparisons are case-sensitive by default.

        Extracts string values from Python INSERT statements, then scans HTML <option value>
        and JS string literals for the same strings appearing with different casing.
        Zero-LLM, regex-only.
        """
        py_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".py")}
        js_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".js")}
        html_files = {p: c for p, c in ctx.generated_files.items() if p.endswith(".html")}

        # Step 1: Extract string literals from Python INSERT INTO ... VALUES (...) blocks
        _SEED_VALUE_RE = re.compile(
            r"INSERT\s+INTO[^;()]*VALUES\s*\([^)]*?['\"]([A-Za-z][A-Za-z\s]{1,30})['\"]",
            re.IGNORECASE | re.DOTALL,
        )
        seeded_values: dict[str, str] = {}  # lowercased → original
        primary_py = ""
        for py_path, content in py_files.items():
            if not primary_py:
                primary_py = py_path
            for m in _SEED_VALUE_RE.finditer(content):
                val = m.group(1).strip()
                if len(val) >= 3:  # skip very short strings to reduce false positives
                    seeded_values[val.lower()] = val

        if not seeded_values:
            return []

        # Step 2: Scan HTML <option value="..."> and JS quoted string literals
        _OPTION_VALUE_RE = re.compile(r'<option[^>]+value=["\']([^"\']+)["\']', re.IGNORECASE)
        _JS_STRING_RE = re.compile(r'["\']([A-Za-z][A-Za-z\s]{1,30})["\']')

        errors: List[Dict[str, Any]] = []
        seen_pairs: set[tuple[str, str]] = set()  # (file, value) dedup

        frontend_files = {**html_files, **js_files}
        for fe_path, content in frontend_files.items():
            # Collect candidates from <option value> and string literals
            candidates: set[str] = set(_OPTION_VALUE_RE.findall(content))
            for m in _JS_STRING_RE.finditer(content):
                candidates.add(m.group(1))

            for cand in candidates:
                cand_lower = cand.lower()
                if cand_lower not in seeded_values:
                    continue
                original = seeded_values[cand_lower]
                if cand == original:
                    continue  # case matches — no problem
                pair_key = (fe_path, cand_lower)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                errors.append(
                    {
                        "file_a": fe_path,
                        "file_b": primary_py,
                        "error_type": "case_mismatch_constant",
                        "description": (
                            f"'{fe_path}' uses '{cand}' but Python seeds '{original}' — "
                            "case mismatch will cause silent lookup failures"
                        ),
                        "suggestion": (
                            f"Change '{cand}' to '{original}' in {fe_path}, "
                            "or normalize both sides with .lower() / LOWER() in SQL"
                        ),
                    }
                )

        if errors:
            ctx.logger.info(f"[CrossFileValidation] I6 Pass 9: {len(errors)} case-mismatch constant(s) found")
        return errors
