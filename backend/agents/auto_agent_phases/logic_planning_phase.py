"""Logic Planning Phase - Creates detailed implementation plans for each file."""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase
from backend.utils.domains.auto_generation.prompt_templates import AutoGenPrompts


class LogicPlanningPhase(IAgentPhase):
    """
    Phase 2.5 (between Structure and FileContentGeneration):
    Creates a detailed implementation plan for each file, specifying:
    - What the file should do
    - Key functions/classes to implement
    - Dependencies and interactions
    - Validation criteria

    This plan is then used by FileContentGenerationPhase to generate accurate content.
    """

    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(
        self,
        project_description: str,
        project_name: str,
        project_root: Path,
        readme_content: str,
        initial_structure: Dict[str, Any],
        generated_files: Dict[str, str],
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        file_paths = kwargs.get("file_paths", [])
        self.context.logger.info(
            f"[PROJECT_NAME:{project_name}] PHASE 2.5: Creating detailed logic plans for {len(file_paths)} files..."
        )
        self.context.event_publisher.publish("phase_start", phase="2.5", message="Creating logic implementation plans")

        logic_plan = {}

        # Group files by type/purpose
        files_by_category = self._categorize_files(file_paths)

        for category, files in files_by_category.items():
            # F32: Increase limit to 15 files per category for better coverage
            files_to_plan = files[:15]
            self.context.logger.info(f"  Planning {category}: {len(files_to_plan)} files (limited from {len(files)})")

            # Generate a plan for this category
            category_plan = await self._plan_category(
                category, files_to_plan, project_description, readme_content, initial_structure
            )

            for file_path, plan in category_plan.items():
                logic_plan[file_path] = plan

        # Save plan to disk
        plan_file = project_root / "IMPLEMENTATION_PLAN.json"
        self.context.file_manager.write_file(plan_file, json.dumps(logic_plan, indent=2))
        generated_files["IMPLEMENTATION_PLAN.json"] = json.dumps(logic_plan, indent=2)

        # Store in context for FileContentGenerationPhase to use
        self.context.logic_plan = logic_plan

        self.context.event_publisher.publish(
            "phase_complete",
            phase="2.5",
            message=f"Logic plan created for {len(logic_plan)} files",
        )
        self.context.logger.info(
            f"[PROJECT_NAME:{project_name}] PHASE 2.5 complete: Plans created for {len(logic_plan)} files"
        )

        return generated_files, initial_structure, file_paths

    def _categorize_files(self, file_paths: List[str]) -> Dict[str, List[str]]:
        """Group files by their category (config, main logic, utilities, tests, etc)."""
        categories = {
            "config": [],
            "main": [],
            "utils": [],
            "tests": [],
            "docs": [],
            "web": [],
            "other": [],
        }

        for file_path in file_paths:
            if any(x in file_path for x in ["config", "settings", "env"]):
                categories["config"].append(file_path)
            elif any(x in file_path for x in ["test", "spec"]):
                categories["tests"].append(file_path)
            elif any(x in file_path for x in ["utils", "helper", "lib"]):
                categories["utils"].append(file_path)
            elif any(x in file_path for x in [".html", ".css", ".js", "web", "static"]):
                categories["web"].append(file_path)
            elif any(x in file_path for x in [".md", "README", "LICENSE"]):
                categories["docs"].append(file_path)
            elif any(x in file_path for x in ["main", "app", "server", "index", "__main__"]):
                categories["main"].append(file_path)
            else:
                categories["other"].append(file_path)

        # Remove empty categories
        return {k: v for k, v in categories.items() if v}

    async def _plan_category(
        self,
        category: str,
        files: List[str],
        project_description: str,
        readme_content: str,
        initial_structure: Dict[str, Any],
    ) -> Dict[str, Dict]:
        """Create detailed plans for files in a category using DB/YAML prompts."""
        
        files_list = "\n".join(f"- {f}" for f in files)
        system_prompt, user_prompt = AutoGenPrompts.architecture_planning_detailed(
            category=category,
            files_list=files_list,
            project_description=project_description
        )

        try:
            response_data, _ = self.context.llm_manager.get_client("planner").chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                tools=[],
                options_override={"temperature": 0.4},
            )

            response_text = response_data.get("content", "")

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                plans = json.loads(json_match.group())
                # Validation: Ensure plans are not empty and contain requested files
                if not plans or not any(f in plans for f in files):
                    raise ValueError("LLM returned empty or irrelevant planning JSON")
            else:
                plans = self._create_basic_plans(files, category, project_description)

            return plans

        except Exception as e:
            self.context.logger.error(f"Error planning category {category}: {e}")
            return self._create_basic_plans(files, category, project_description)

    def _create_basic_plans(self, files: List[str], category: str, project_description: str) -> Dict[str, Dict]:
        """Create basic fallback plans anchored to the original project description."""
        plans = {}
        
        # Validation: If project_description is too short, we might be losing intent
        if len(project_description) < 10:
             self.context.logger.warning("Project description is critically short for fallback planning.")

        for file_path in files:
            ext = Path(file_path).suffix
            purpose = f"Implementation of {category} logic for: {project_description[:100]}..."
            exports = []

            if category == "config":
                purpose = "System configuration and environment settings."
                exports = ["Config", "get_config"]
            elif category == "main":
                purpose = f"Main entry point for {project_description[:50]}"
                exports = ["main", "app"]
            
            plans[file_path] = {
                "purpose": purpose,
                "exports": exports,
                "imports": [],
                "main_logic": [f"Develop core {category} logic aligned with: {project_description}"],
                "validation": ["Verify alignment with initial project intent", "Execute unit tests"],
                "dependencies": [],
            }

        return plans
