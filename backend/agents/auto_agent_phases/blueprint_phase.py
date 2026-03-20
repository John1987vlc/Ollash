"""Phase 2: BlueprintPhase — one LLM call to produce the full project blueprint.

Replaces: ReadmeGenerationPhase + StructureGenerationPhase + LogicPlanningPhase
(3 heavy phases → 1 focused call).

Output: ctx.blueprint (List[FilePlan]) sorted by priority.
Prompt: prompts/domains/auto_generation/blueprint.yaml
"""

from __future__ import annotations

import dataclasses
from collections import deque

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.blueprint_models import BlueprintOutput
from backend.agents.auto_agent_phases.phase_context import FilePlan, PhaseContext

# ── Fallback prompts (used when YAML can't be loaded) ────────────────────────

# Large-model fallback (≥9B): up to 20 files, pretty JSON
_SYSTEM_FALLBACK = """# ROLE
Software Architect. Output JSON only. No markdown. No prose.

# TASK
Given a project description, produce a complete project blueprint as JSON.

# RULES
- Maximum 20 files total.
- Files that are depended upon MUST have a lower priority number than their dependents.
- The "imports" field lists OTHER project files (not pip packages).
- Output ONLY valid JSON. No markdown fences. No explanations.

# EXAMPLE
Input: "A Python CLI that converts CSV to JSON"
Output:
{"project_type":"cli","tech_stack":["python"],"files":[
  {"path":"src/converter.py","purpose":"CSV to JSON logic","exports":["convert_csv"],"imports":[],"key_logic":"csv.DictReader → json.dumps","priority":1},
  {"path":"cli.py","purpose":"CLI entry point","exports":[],"imports":["src/converter.py"],"key_logic":"argparse --input/--output flags","priority":2}
]}"""

_USER_TEMPLATE = """Project name: {project_name}
Description: {project_description}
Detected type: {project_type}
Detected stack: {tech_stack}

Output blueprint JSON now (max 20 files):"""

# Small-model fallback (≤8B): 5 files max, MINIFIED single-line JSON
_SYSTEM_FALLBACK_SMALL = """Output ONLY a single-line minified JSON object. No markdown. No prose. No newlines.

SCHEMA: {"project_type":"...","tech_stack":[...],"files":[{"path":"...","purpose":"...","exports":[...],"imports":[...],"key_logic":"...","priority":1}]}

RULES:
- Maximum {max_files} files (core code only, no README, no config files).
- Lower priority number = generated first.
- "imports" lists only other project files.
- Output starts with { and ends with } on a SINGLE LINE.
- For frontend JS files: key_logic MUST list every DOM id accessed, e.g. "reads #pot, #board; writes #status, #btn-fold".
- index.html key_logic MUST include a <div id=xxx> for EVERY id that JS files reference.
- For files with complex algorithms (game logic, parsers, evaluators): key_logic MUST also list every function signature that must exist, e.g. "isFlush(cards):bool, isStraight(cards):bool, evaluateHand(hole,community):{rank,name}, resolveShowdown(players,community):winner".

EXAMPLE (frontend card game):
{"project_type":"frontend_web","tech_stack":["html","javascript","css"],"files":[{"path":"styles.css","purpose":"Card and layout styles","exports":[],"imports":[],"key_logic":".card,.game-board,.stats-panel classes; CSS vars for colors; flexbox grid","priority":1},{"path":"data.js","purpose":"Card definitions and viability report","exports":["cards","generateViabilityReport"],"imports":[],"key_logic":"window.cards=array of {id,name,type,cost,damage}; window.generateViabilityReport()=aggregates stats; reads no DOM — NO module.exports","priority":2},{"path":"game.js","purpose":"Game logic and DOM rendering","exports":["initGame"],"imports":["data.js","styles.css"],"key_logic":"window.initGame() renders .card SVG elements into #game-board; reads #game-board, #stats-panel, #btn-start; shows result in #stats-panel — NO require()","priority":3},{"path":"index.html","purpose":"Entry point","exports":[],"imports":["styles.css","data.js","game.js"],"key_logic":"<link href=styles.css>; <script src=data.js defer>; <script src=game.js defer>; <div id=game-board>; <div id=stats-panel>; <button id=btn-start>; DOMContentLoaded calls window.initGame()","priority":4}]}"""

_USER_TEMPLATE_SMALL = """Project: {project_name}
Description: {project_description}
Type: {project_type}
Stack: {tech_stack}

Output MINIFIED JSON blueprint (max {max_files} files, single line):"""


class BlueprintPhase(BasePhase):
    phase_id = "2"
    phase_label = "Blueprint"

    def run(self, ctx: PhaseContext) -> None:
        system, user_template = self._load_prompt(ctx)

        max_files = self._dynamic_max_files(ctx)  # #15 dynamic limit
        ctx.metrics["blueprint_max_files"] = max_files

        # For small models the system fallback and user template both contain {max_files}
        if ctx.is_small():
            system = system.replace("{max_files}", str(max_files))
            user = user_template.format(
                project_name=ctx.project_name,
                project_description=ctx.project_description[:1200],
                project_type=ctx.project_type,
                tech_stack=", ".join(ctx.tech_stack),
                max_files=max_files,
            )
        else:
            user = user_template.format(
                project_name=ctx.project_name,
                project_description=ctx.project_description[:1200],
                project_type=ctx.project_type,
                tech_stack=", ".join(ctx.tech_stack),
            )
            # Append dynamic max_files hint so the LLM respects the adjusted limit
            user = user.rstrip() + f"\n\nConstraint: generate at most {max_files} files for this project."
            # M4 — Inject mandatory pattern hints for FastAPI+HTML+SQLite projects
            mandatory_hints = self._build_mandatory_hints(ctx)
            if mandatory_hints:
                user = user.rstrip() + f"\n\n{mandatory_hints}"

        result: BlueprintOutput = self._llm_json(
            ctx,
            system,
            user,
            schema_class=BlueprintOutput,
            role="planner",
            retries=2,
        )

        # Update detected values if the LLM refined them
        if result.project_type and result.project_type != "unknown":
            ctx.project_type = result.project_type
        if result.tech_stack:
            ctx.tech_stack = result.tech_stack

        # #I1 — Deduplicate files by path (keep last occurrence per path)
        seen_paths: dict[str, int] = {}
        for idx, f in enumerate(result.files):
            seen_paths[f.path] = idx  # overwrite → last wins
        if len(seen_paths) < len(result.files):
            dupes = len(result.files) - len(seen_paths)
            ctx.logger.warning(
                f"[Blueprint] {dupes} duplicate path(s) in LLM response — keeping last occurrence per path"
            )
            deduped = [result.files[i] for i in sorted(seen_paths.values())]
            result = result.model_copy(update={"files": deduped})

        # Convert to FilePlan dataclasses, sorted by priority
        ctx.blueprint = sorted(
            [
                FilePlan(
                    path=f.path,
                    purpose=f.purpose,
                    exports=f.exports,
                    imports=f.imports,
                    key_logic=f.key_logic,
                    priority=f.priority,
                )
                for f in result.files
            ],
            key=lambda fp: fp.priority,
        )

        # I5 — Repair dependency cycles before topological sort (removes back edges)
        ctx.blueprint, edges_removed = self._repair_cycles(ctx.blueprint)
        if edges_removed:
            ctx.logger.warning(f"[Blueprint] I5: Removed {edges_removed} back-edge(s) to break dependency cycle(s)")
            ctx.metrics["blueprint_cycles_repaired"] = edges_removed

        # Bug 1 — Enforce dependency order via topological sort (now guaranteed on repaired graph)
        ctx.blueprint = self._topological_sort(ctx.blueprint)

        # I2 — Sync HTML entrypoint key_logic with all DOM IDs referenced by JS files
        self._validate_and_patch_html_entrypoint_key_logic(ctx)

        # M3 — Post-process: guarantee essential files are present
        self._ensure_mandatory_files(ctx)

        # S3-2 — Enforce files explicitly mentioned in description: auto-inject missing ones
        self._enforce_described_files(ctx)

        # Bug 4 — Merge dependent JS pairs on small models to prevent dual implementations
        self._merge_dependent_js_for_small_models(ctx)

        # #3 — Validate that import graph is a DAG (informational — should be 0 after I5)
        cycles = self._detect_dag_cycles(ctx.blueprint)
        if cycles:
            for cycle in cycles:
                ctx.logger.warning(f"[Blueprint] Residual cycle (unexpected after I5): {' → '.join(cycle)}")
            ctx.errors.append(f"Blueprint: {len(cycles)} residual dependency cycle(s) after repair")

        ctx.logger.info(
            f"[Blueprint] {len(ctx.blueprint)} files planned, type={ctx.project_type}, stack={ctx.tech_stack}"
        )

        ctx.event_publisher.publish_sync(
            "blueprint_ready",
            files=[{"path": fp.path, "purpose": fp.purpose} for fp in ctx.blueprint],
            project_type=ctx.project_type,
            tech_stack=ctx.tech_stack,
        )

    # ----------------------------------------------------------------
    # Bug 1 — Topological sort (Kahn's BFS)
    # ----------------------------------------------------------------

    @staticmethod
    def _topological_sort(plans: list) -> list:
        """Topological sort of the file import graph using Kahn's BFS algorithm.

        Ensures each file is generated only after all its declared imports,
        regardless of the LLM-assigned priority numbers.

        Tie-breaking: among simultaneously eligible nodes, the original priority
        number (ascending) is used to preserve the LLM's intent for independent files.

        Reassigns sequential priority integers (1, 2, 3, …) on the result so that
        _group_by_priority() in CodeFillPhase doesn't batch dependent files together.

        Returns the reordered list when the graph is a valid DAG.
        Returns the input list unchanged when a cycle is detected (defensive fallback).
        """
        path_to_plan = {p.path: p for p in plans}
        all_paths = set(path_to_plan)

        in_degree: dict[str, int] = {p.path: 0 for p in plans}
        dependents: dict[str, list[str]] = {p.path: [] for p in plans}

        for p in plans:
            for dep in p.imports:
                if dep in all_paths:
                    in_degree[p.path] += 1
                    dependents[dep].append(p.path)

        # Seed queue with zero-in-degree nodes, ordered by original priority
        queue: deque[str] = deque(
            sorted(
                [path for path, deg in in_degree.items() if deg == 0],
                key=lambda path: path_to_plan[path].priority,
            )
        )
        result: list[FilePlan] = []
        while queue:
            node = queue.popleft()
            result.append(path_to_plan[node])
            for dependent in dependents[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
            # Re-sort to maintain priority tie-breaking among newly eligible nodes
            queue = deque(sorted(queue, key=lambda path: path_to_plan[path].priority))

        if len(result) != len(plans):
            # Cycle detected — fall back to original list (cycle warning logged separately)
            return plans

        # Reassign sequential priorities so CodeFillPhase sees a strict linear order
        return [dataclasses.replace(fp, priority=i + 1) for i, fp in enumerate(result)]

    # ----------------------------------------------------------------
    # I2 — Sync HTML entrypoint key_logic with all DOM IDs from JS
    # ----------------------------------------------------------------

    @staticmethod
    def _validate_and_patch_html_entrypoint_key_logic(ctx: PhaseContext) -> None:
        """Collect every #id mentioned in JS key_logic fields and inject any
        missing ones into the HTML entrypoint's key_logic so that
        CodeFillPhase._build_dom_contract produces a complete DOM contract.

        The HTML entrypoint is the HTML file generated last (highest priority
        number after topological sort).
        """
        import re

        if not ctx.blueprint:
            return

        has_html = any(fp.path.endswith(".html") for fp in ctx.blueprint)
        has_js = any(fp.path.endswith(".js") for fp in ctx.blueprint)
        if not (has_html and has_js):
            return

        # Collect all #ids from JS key_logic
        js_ids: set[str] = set()
        for fp in ctx.blueprint:
            if fp.path.endswith(".js") and fp.key_logic:
                js_ids.update(re.findall(r"#([\w-]+)", fp.key_logic))

        if not js_ids:
            return

        # Find HTML entrypoint = HTML file with highest priority (generated last)
        html_files = [fp for fp in ctx.blueprint if fp.path.endswith(".html")]
        entrypoint = max(html_files, key=lambda fp: fp.priority)

        # Find IDs missing from the entrypoint key_logic
        existing_ids: set[str] = set(re.findall(r"#([\w-]+)", entrypoint.key_logic or ""))
        # Also match bare id=X (without #) that may already be in key_logic
        existing_ids.update(re.findall(r"<div\s+id=([\w-]+)", entrypoint.key_logic or ""))
        missing = js_ids - existing_ids
        if not missing:
            return

        injected: list[str] = []
        new_key_logic = entrypoint.key_logic or ""
        for dom_id in sorted(missing):
            new_key_logic += f"<div id={dom_id}>"
            injected.append(f"#{dom_id}")

        # Replace the entrypoint entry in ctx.blueprint with updated key_logic
        ctx.blueprint = [
            dataclasses.replace(fp, key_logic=new_key_logic) if fp is entrypoint else fp for fp in ctx.blueprint
        ]

        ctx.logger.info(
            f"[Blueprint] EntrypointFix: injected {len(injected)} missing DOM id(s) "
            f"into {entrypoint.path}: {', '.join(injected)}"
        )

    # ----------------------------------------------------------------
    # Bug 4 — Merge dependent JS pairs for small models
    # ----------------------------------------------------------------

    @staticmethod
    def _merge_dependent_js_for_small_models(ctx: PhaseContext) -> None:
        """Merge a JS file that imports another JS file into a single file on small (≤8B) models.

        Prevents the pattern where two independent LLM calls each implement the full
        game/app logic and expose conflicting window.* globals.

        Only merges when:
        - Model is small (≤8B)
        - There are ≥2 JS files in the blueprint
        - A JS file A imports exactly one other JS file B
        - B itself has no JS imports (avoids complex chain merges)
        - The importer file A is NOT explicitly named in the project description
          (if the user explicitly requested a specific file, we preserve it)

        The dependency (B) becomes the merged host file. A's exports/purpose/key_logic
        are merged in. Any other file that imported A now imports B instead.
        """
        if not ctx.is_small():
            return

        js_plans = [fp for fp in ctx.blueprint if fp.path.endswith(".js")]
        if len(js_plans) < 2:
            return

        import re as _re

        # Files explicitly named in the description — never merge these away
        mentioned_files = set(_re.findall(r"\b(\w+(?:/\w+)*\.\w{2,5})\b", ctx.project_description))

        all_paths = {fp.path for fp in ctx.blueprint}

        for importer in js_plans:
            js_deps = [dep for dep in importer.imports if dep.endswith(".js") and dep in all_paths]
            if len(js_deps) != 1:
                continue
            dep_path = js_deps[0]
            dep_plan = next((fp for fp in ctx.blueprint if fp.path == dep_path), None)
            if dep_plan is None:
                continue
            # Skip if the dependency itself imports JS files (chain too complex)
            if any(d.endswith(".js") and d in all_paths for d in dep_plan.imports):
                continue
            # Skip if the importer is explicitly requested in the description
            if importer.path in mentioned_files:
                ctx.logger.info(
                    f"[Blueprint] B4: Skipping merge of '{importer.path}' into '{dep_path}'"
                    " — file explicitly named in description; preserving separate file"
                )
                continue

            merged_exports = list(dict.fromkeys(dep_plan.exports + importer.exports))
            merged_purpose = f"{dep_plan.purpose}; {importer.purpose}"
            merged_key_logic = f"{dep_plan.key_logic}\n{importer.key_logic}".strip()
            merged_imports = [d for d in importer.imports if not d.endswith(".js")]

            merged_plan = dataclasses.replace(
                dep_plan,
                exports=merged_exports,
                purpose=merged_purpose,
                key_logic=merged_key_logic,
                imports=merged_imports,
            )

            # Remove importer, replace dep with merged; redirect any imports of A → B
            new_blueprint: list[FilePlan] = []
            for fp in ctx.blueprint:
                if fp.path == importer.path:
                    continue
                if fp.path == dep_path:
                    new_blueprint.append(merged_plan)
                elif importer.path in fp.imports:
                    # Replace A with B, then deduplicate (B may already be in the list)
                    redirected = [dep_path if imp == importer.path else imp for imp in fp.imports]
                    new_imports = list(dict.fromkeys(redirected))
                    new_blueprint.append(dataclasses.replace(fp, imports=new_imports))
                else:
                    new_blueprint.append(fp)

            ctx.blueprint = new_blueprint
            ctx.logger.info(
                f"[Blueprint] B4: Merged JS '{importer.path}' into '{dep_path}'"
                " (small model — prevents duplicate implementation)"
            )
            ctx.metrics["blueprint_js_merge"] = True
            break  # one merge per run to avoid cascading issues

    # ----------------------------------------------------------------
    # #3 — DAG cycle detection
    # ----------------------------------------------------------------

    @staticmethod
    def _repair_cycles(plans: list) -> tuple:
        """I5: Break dependency cycles by removing the back edge that forms each cycle.

        Strategy: find cycle [A→B→C→A], remove the import edge C→A (the "back edge"
        — the last node's edge back to the cycle start). Repeat until no cycles remain.
        Uses dataclasses.replace() to rebuild immutable FilePlan entries.

        Returns (repaired_plans, edges_removed_count).
        """
        import dataclasses

        all_paths = {p.path for p in plans}
        # Build mutable import graph (path → list of imported paths)
        repaired: dict = {p.path: list(p.imports) for p in plans}
        removed = 0

        for _ in range(len(plans) + 1):  # safety: max iterations = plan count + 1
            # Build current adjacency
            graph: dict = {path: [d for d in deps if d in all_paths] for path, deps in repaired.items()}

            # DFS cycle detection — find the first cycle
            visited: set = set()
            rec_stack: set = set()
            found_cycle: list = []

            def _dfs(node: str, path: list) -> bool:
                visited.add(node)
                rec_stack.add(node)
                path.append(node)
                for neighbor in graph.get(node, []):
                    if neighbor not in visited:
                        if _dfs(neighbor, path):
                            return True
                    elif neighbor in rec_stack:
                        cycle_start = path.index(neighbor)
                        found_cycle.extend(path[cycle_start:] + [neighbor])
                        return True
                path.pop()
                rec_stack.discard(node)
                return False

            for node in graph:
                if node not in visited:
                    if _dfs(node, []):
                        break

            if not found_cycle:
                break  # no more cycles — done

            # found_cycle = [A, B, C, A] — remove back edge C→A
            back_src = found_cycle[-2]
            back_dst = found_cycle[0]
            current_deps = repaired.get(back_src, [])
            if back_dst in current_deps:
                repaired[back_src] = [d for d in current_deps if d != back_dst]
                removed += 1
            else:
                break  # safety: cycle exists but back edge not found — avoid infinite loop

        # Rebuild FilePlan list with repaired imports
        result = []
        for p in plans:
            new_imports = repaired.get(p.path, list(p.imports))
            if new_imports != list(p.imports):
                result.append(dataclasses.replace(p, imports=new_imports))
            else:
                result.append(p)
        return result, removed

    @staticmethod
    def _detect_dag_cycles(blueprint) -> list:
        """Detect cycles in the file import graph using iterative DFS.

        Returns a list of cycles, each cycle is a list of file paths forming the loop.
        An empty list means the graph is a valid DAG.
        """
        from typing import Dict, List, Set

        # Build adjacency: path -> list of imported paths (only those in blueprint)
        all_paths = {fp.path for fp in blueprint}
        graph: Dict[str, List[str]] = {fp.path: [dep for dep in fp.imports if dep in all_paths] for fp in blueprint}

        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        cycles: list = []

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    # Found a cycle — extract the cycle portion
                    cycle_start = path.index(neighbor)
                    cycles.append(path[cycle_start:] + [neighbor])
            path.pop()
            rec_stack.discard(node)

        for node in graph:
            if node not in visited:
                dfs(node, [])

        return cycles

    # ----------------------------------------------------------------
    # #15 — Dynamic max_files based on description complexity
    # ----------------------------------------------------------------

    @staticmethod
    def _dynamic_max_files(ctx: PhaseContext) -> int:
        """Adjust blueprint file limit based on model size and description complexity.

        #I2 — api+db combo gets a higher floor: these stacks require models, schemas,
        routers, DB init, requirements.txt, etc. and always exceed the generic baseline.
        """
        _MULTI_FILE_TYPES = {
            "game",
            "frontend_web",
            "full_stack",
            "full_stack_web",
            "python_app",
            "api",
            "web_app",
            "react_app",
            "flutter_app",
            "java_app",
            "csharp_app",
            "kotlin_app",
        }
        _API_TYPES = {"api", "full_stack", "full_stack_web", "web_app", "python_app", "csharp_app"}
        _DB_KEYWORDS = {"sqlite", "postgresql", "mysql", "mongodb", "redis", "postgres"}

        stack_lower = {t.lower() for t in ctx.tech_stack}
        has_db = bool(stack_lower & _DB_KEYWORDS)

        if ctx.is_small():
            # B3 — games, full-stack, and Python web apps need more files
            # #I2 — api+db on small models: bump from 7 → 9
            if ctx.project_type in _MULTI_FILE_TYPES:
                return 9 if has_db else 7
            return 5  # Hard cap for small models on simple projects

        # Large model path
        # #I2 — api+db always earns at least 14 file slots regardless of complexity score
        has_api = ctx.project_type in _API_TYPES
        api_db_floor = 14 if (has_api and has_db) else 0

        complexity = ctx.description_complexity()
        if complexity <= 2:
            base = 8  # Simple project: keep it lean
        elif complexity <= 5:
            base = 14  # Medium project
        else:
            base = 20  # Complex project: full budget
        return max(base, api_db_floor)

    # ----------------------------------------------------------------
    # M3 — Mandatory file injection
    # ----------------------------------------------------------------

    @staticmethod
    def _ensure_mandatory_files(ctx: PhaseContext) -> None:
        """Post-process: guarantee essential files are in the blueprint.

        Rule: If CSS is in tech_stack but no .css file is planned, and at least
        one .html file IS planned, insert static/style.css at priority 1 so it
        is generated before the HTML files that reference it.
        """
        css_in_stack = "css" in [t.lower() for t in ctx.tech_stack]
        has_css = any(fp.path.endswith(".css") for fp in ctx.blueprint)
        has_html = any(fp.path.endswith(".html") for fp in ctx.blueprint)

        if css_in_stack and has_html and not has_css:
            css_plan = FilePlan(
                path="static/style.css",
                purpose="Main stylesheet for all pages",
                exports=[],
                imports=[],
                key_logic=(
                    "CSS custom properties (--primary-color, --bg-color) for theming; "
                    "responsive flexbox layout; form, table, button, and nav styles; "
                    "status badge classes (.status-pending, .status-cancelled)"
                ),
                priority=1,
            )
            # Insert at front; sorted() is stable so priority=1 entries keep relative order
            ctx.blueprint = [css_plan] + ctx.blueprint
            ctx.logger.info("[Blueprint] M3: Auto-added static/style.css (CSS in stack, no .css planned)")

    # ----------------------------------------------------------------
    # M4 — Mandatory hints for FastAPI+HTML+SQLite (large models only)
    # ----------------------------------------------------------------

    @staticmethod
    def _build_mandatory_hints(ctx: PhaseContext) -> str:
        """Return mandatory pattern hints for the blueprint LLM prompt.

        Only emitted for large (>8B) models where the token budget allows it.
        Targets FastAPI + HTML + SQLite projects — the combination most likely to
        produce missing StaticFiles, init_db-only-in-main, and missing list endpoints.
        """
        # Small models: budget too tight
        if ctx.is_small():
            return ""

        has_fastapi = "fastapi" in [t.lower() for t in ctx.tech_stack]
        has_html = "html" in [t.lower() for t in ctx.tech_stack]
        has_sqlite = "sqlite" in [t.lower() for t in ctx.tech_stack]
        is_web_api = ctx.project_type in ("api", "python_app", "web_app", "full_stack_web", "full_stack")

        if not (has_fastapi and has_html and is_web_api):
            return ""

        lines = ["MANDATORY — the Python entry point's key_logic field MUST include:"]
        lines.append("- app.mount('/static', StaticFiles(directory='static'), name='static')")
        if has_sqlite:
            lines.append("- @app.on_event('startup') to call init_db() — NOT only in if __name__=='__main__'")
            lines.append("- Use 'with sqlite3.connect(DB) as conn:' context manager — no manual conn.close()")
        lines.append("- GET /api/<resource> endpoint returning ALL records as a list (not only by ID)")
        return "\n".join(lines)

    def _load_prompt(self, ctx: PhaseContext) -> tuple[str, str]:
        """Load from YAML; fall back to tier-appropriate inline constants."""
        small = ctx.is_small()
        system_fb = _SYSTEM_FALLBACK_SMALL if small else _SYSTEM_FALLBACK
        user_fb = _USER_TEMPLATE_SMALL if small else _USER_TEMPLATE

        try:
            from backend.utils.core.llm.prompt_loader import PromptLoader

            loader = PromptLoader()
            key = "generate_blueprint_small" if small else "generate_blueprint"
            prompts = loader.load_prompt_sync("domains/auto_generation/blueprint.yaml")
            if prompts and key in prompts:
                tmpl = prompts[key]
                return tmpl.get("system", system_fb), tmpl.get("user", user_fb)
        except Exception as exc:
            ctx.logger.debug(f"[Blueprint] YAML load failed ({exc}); using inline fallback")
        return system_fb, user_fb

    # ----------------------------------------------------------------
    # S3-2 — Description coverage check
    # ----------------------------------------------------------------

    @staticmethod
    def _enforce_described_files(ctx: PhaseContext) -> None:
        """Auto-inject files mentioned in the description but absent from the blueprint.

        Uses a conservative filename regex to avoid false positives on natural-language
        text (e.g. 'e.g.' or 'i.e.' are excluded by requiring at least 2-char extension).

        Injection constraints:
        - Capped at 3 files for small models (token budget); unlimited for large models.
        - Priority = max existing priority + 1 (generate after all currently planned files).
        - Purpose inferred from text following the filename in the description.
        - Files beyond the cap are still logged as warnings for the user.
        """
        import re as _re

        # Match "word/word.ext" or "word.ext" with 2-5 char extension
        mentioned = set(_re.findall(r"\b(\w+(?:/\w+)*\.\w{2,5})\b", ctx.project_description))
        if not mentioned:
            return

        planned_norm = {fp.path.replace("\\", "/") for fp in ctx.blueprint}

        missing = {m for m in mentioned if m.replace("\\", "/") not in planned_norm}
        # Filter out common false positives (version strings, domain names, etc.)
        _FALSE_POSITIVE_EXTS = {".io", ".py2", ".py3"}
        missing = {m for m in missing if not any(m.endswith(e) for e in _FALSE_POSITIVE_EXTS)}

        if not missing:
            return

        ctx.logger.warning(
            f"[Blueprint] Files mentioned in description but not in blueprint: "
            f"{sorted(missing)} — auto-injecting where possible"
        )

        # Cap injections to avoid overwhelming small models
        inject_cap = 3 if ctx.is_small() else len(missing)
        to_inject = sorted(missing)[:inject_cap]

        max_priority = max((fp.priority for fp in ctx.blueprint), default=0)

        for i, path in enumerate(to_inject):
            # Infer purpose: grab up to ~40 chars of text following the filename
            m = _re.search(
                _re.escape(path) + r"\s+([A-Za-z][A-Za-z0-9_\s]{0,40}?)(?:[.,;\n]|$)",
                ctx.project_description,
            )
            purpose = m.group(1).strip() if m else f"Implementation of {path}"

            # #I4 — Derive key_logic from description context around the filename
            kl_match = _re.search(
                _re.escape(path) + r"[^.]{0,120}",
                ctx.project_description,
                _re.IGNORECASE | _re.DOTALL,
            )
            if kl_match:
                raw_kl = kl_match.group(0).replace(path, "").strip(" ,;:\n")
                key_logic = raw_kl[:100] if raw_kl else f"implement {path} as described"
            else:
                key_logic = f"implement {path} as described"

            injected = FilePlan(
                path=path,
                purpose=purpose,
                exports=[],
                imports=[],
                key_logic=key_logic,
                priority=max_priority + 1 + i,
            )
            ctx.blueprint.append(injected)
            ctx.logger.info(f"[Blueprint] Coverage gap auto-injected: '{path}' (priority={injected.priority})")

        # Files beyond the cap: warn only
        for path in sorted(missing)[inject_cap:]:
            ctx.logger.warning(f"[Blueprint] Coverage gap skipped (cap reached): '{path}' — add manually if needed")
            ctx.errors.append(f"Blueprint coverage gap (skipped): '{path}' described but not planned")
