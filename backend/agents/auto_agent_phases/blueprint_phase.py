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

# Fallback inline system prompt if the YAML can't be loaded
_SYSTEM_FALLBACK = """# ROLE
Software Architect. Output JSON only. No markdown. No prose.

# TASK
Given a project description, produce a complete project blueprint as JSON.

# RULES
- Maximum 20 files total. For small models, 10-15 files is ideal.
- Files that are depended upon MUST have a lower priority number than their dependents.
- The "imports" field lists OTHER project files (not pip packages).
- Output ONLY valid JSON. No markdown fences. No explanations.

# OUTPUT SCHEMA
{
  "project_type": "api",
  "tech_stack": ["python", "fastapi"],
  "files": [
    {
      "path": "main.py",
      "purpose": "FastAPI app entry point",
      "exports": ["app"],
      "imports": ["src/routes/users.py"],
      "key_logic": "Creates FastAPI app, mounts routers, runs uvicorn",
      "priority": 2
    },
    {
      "path": "src/routes/users.py",
      "purpose": "User CRUD endpoints",
      "exports": ["router"],
      "imports": ["src/models/user.py"],
      "key_logic": "GET/POST/DELETE /users endpoints with Pydantic validation",
      "priority": 1
    }
  ]
}

# EXAMPLE: Simple CLI tool
Input: "A Python CLI that converts CSV to JSON"
Output:
{"project_type":"cli","tech_stack":["python"],"files":[
  {"path":"src/converter.py","purpose":"CSV to JSON conversion logic","exports":["convert_csv"],"imports":[],"key_logic":"Uses csv.DictReader, returns json string","priority":1},
  {"path":"cli.py","purpose":"CLI entry point using argparse","exports":[],"imports":["src/converter.py"],"key_logic":"argparse with --input/--output flags, calls convert_csv","priority":2},
  {"path":"requirements.txt","purpose":"Python dependencies (stdlib only for this project)","exports":[],"imports":[],"key_logic":"empty or stdlib only","priority":1}
]}"""

_USER_TEMPLATE = """Project name: {project_name}
Description: {project_description}
Detected type: {project_type}
Detected stack: {tech_stack}

Output the blueprint JSON now. Maximum 20 files. Fewer is better for small models."""


class BlueprintPhase(BasePhase):
    phase_id = "2"
    phase_label = "Blueprint"

    def run(self, ctx: PhaseContext) -> None:
        system, user_template = self._load_prompt(ctx)

        user = user_template.format(
            project_name=ctx.project_name,
            project_description=ctx.project_description[:1200],
            project_type=ctx.project_type,
            tech_stack=", ".join(ctx.tech_stack),
        )

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

        ctx.logger.info(
            f"[Blueprint] {len(ctx.blueprint)} files planned, type={ctx.project_type}, stack={ctx.tech_stack}"
        )

        ctx.event_publisher.publish_sync(
            "blueprint_ready",
            files=[{"path": fp.path, "purpose": fp.purpose} for fp in ctx.blueprint],
            project_type=ctx.project_type,
            tech_stack=ctx.tech_stack,
        )

    def _load_prompt(self, ctx: PhaseContext) -> tuple[str, str]:
        """Load from YAML, fall back to inline constants."""
        try:
            from backend.utils.core.llm.prompt_loader import PromptLoader

            loader = PromptLoader()
            key = "generate_blueprint_small" if ctx.is_small() else "generate_blueprint"
            prompts = loader.load_file("domains/auto_generation/blueprint.yaml")
            if prompts and key in prompts:
                tmpl = prompts[key]
                return tmpl.get("system", _SYSTEM_FALLBACK), tmpl.get("user", _USER_TEMPLATE)
            # Fall through to fallback
        except Exception:
            pass
        return _SYSTEM_FALLBACK, _USER_TEMPLATE
