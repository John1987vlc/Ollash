"""Phase 2: BlueprintPhase — one LLM call to produce the full project blueprint.

Replaces: ReadmeGenerationPhase + StructureGenerationPhase + LogicPlanningPhase
(3 heavy phases → 1 focused call).

Output: ctx.blueprint (List[FilePlan]) sorted by priority.
Prompt: prompts/domains/auto_generation/blueprint.yaml
"""

from __future__ import annotations

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
- Maximum 5 files (core code only, no README, no config files).
- Lower priority number = generated first.
- "imports" lists only other project files.
- Output starts with { and ends with } on a SINGLE LINE.

EXAMPLE (frontend card game):
{"project_type":"frontend_web","tech_stack":["html","javascript","css"],"files":[{"path":"styles.css","purpose":"Card and layout styles","exports":[],"imports":[],"key_logic":".card,.game-board,.stats-panel classes; CSS vars for colors; flexbox grid","priority":1},{"path":"data.js","purpose":"Card definitions and viability report","exports":["cards","generateViabilityReport"],"imports":[],"key_logic":"window.cards=array of {id,name,type,cost,damage}; window.generateViabilityReport()=aggregates stats — NO module.exports","priority":2},{"path":"game.js","purpose":"Game logic and DOM rendering","exports":["initGame"],"imports":["data.js","styles.css"],"key_logic":"window.initGame() renders .card SVG elements into #game-board; calls window.generateViabilityReport(); shows result in #stats-panel — NO require()","priority":3},{"path":"index.html","purpose":"Entry point","exports":[],"imports":["styles.css","data.js","game.js"],"key_logic":"<link href=styles.css>; <script src=data.js defer>; <script src=game.js defer>; <div id=game-board>; <div id=stats-panel>; DOMContentLoaded calls window.initGame()","priority":4}]}"""

_USER_TEMPLATE_SMALL = """Project: {project_name}
Description: {project_description}
Type: {project_type}
Stack: {tech_stack}

Output MINIFIED JSON (max 5 files, single line):"""


class BlueprintPhase(BasePhase):
    phase_id = "2"
    phase_label = "Blueprint"

    def run(self, ctx: PhaseContext) -> None:
        system, user_template = self._load_prompt(ctx)

        max_files = self._dynamic_max_files(ctx)  # #15 dynamic limit
        ctx.metrics["blueprint_max_files"] = max_files

        user = user_template.format(
            project_name=ctx.project_name,
            project_description=ctx.project_description[:1200],
            project_type=ctx.project_type,
            tech_stack=", ".join(ctx.tech_stack),
        )
        # Append dynamic max_files hint so the LLM respects the adjusted limit
        if not ctx.is_small():
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

        # M3 — Post-process: guarantee essential files are present
        self._ensure_mandatory_files(ctx)

        # #3 — Validate that import graph is a DAG (no cycles)
        cycles = self._detect_dag_cycles(ctx.blueprint)
        if cycles:
            for cycle in cycles:
                ctx.logger.warning(f"[Blueprint] Dependency cycle detected: {' → '.join(cycle)}")
            ctx.errors.append(f"Blueprint: {len(cycles)} dependency cycle(s) detected")

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
    # #3 — DAG cycle detection
    # ----------------------------------------------------------------

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
        """Adjust blueprint file limit based on model size and description complexity."""
        if ctx.is_small():
            # B3 — games, full-stack, and Python web apps need more files
            # e.g. app.py + index.html + admin.html + style.css + app.js + requirements.txt = 6
            # M2: added python_app, api, web_app, full_stack_web
            multi_file_types = {
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
            if ctx.project_type in multi_file_types:
                return 7
            return 5  # Hard cap for small models on simple projects
        complexity = ctx.description_complexity()
        if complexity <= 2:
            return 8  # Simple project: keep it lean
        if complexity <= 5:
            return 14  # Medium project
        return 20  # Complex project: full budget

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
