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

        # Accumulate exports from already-planned categories so later categories
        # can see the API contracts and stay consistent (Fix 2)
        already_planned_contracts: Dict[str, List[str]] = {}

        for category, files in files_by_category.items():
            # F32: Increase limit to 15 files per category for better coverage
            files_to_plan = files[:15]
            self.context.logger.info(f"  Planning {category}: {len(files_to_plan)} files (limited from {len(files)})")

            # Generate a plan for this category, passing already-planned contracts
            category_plan = await self._plan_category(
                category, files_to_plan, project_description, readme_content,
                initial_structure, already_planned_contracts
            )

            for file_path, plan in category_plan.items():
                logic_plan[file_path] = plan
                # Register this file's exports so subsequent categories see them
                already_planned_contracts[file_path] = plan.get("exports", [])

        # Save plan to disk
        plan_file = project_root / "IMPLEMENTATION_PLAN.json"
        self.context.file_manager.write_file(plan_file, json.dumps(logic_plan, indent=2))
        generated_files["IMPLEMENTATION_PLAN.json"] = json.dumps(logic_plan, indent=2)

        # NEW: Generate Agile Backlog
        self.context.logger.info("  Generating Agile Backlog of micro-tasks...")
        backlog = await self._generate_backlog(
            project_description, readme_content, initial_structure
        )
        
        backlog_file = project_root / "BACKLOG.json"
        self.context.file_manager.write_file(backlog_file, json.dumps(backlog, indent=2))
        generated_files["BACKLOG.json"] = json.dumps(backlog, indent=2)

        # Store in context for FileContentGenerationPhase to use
        self.context.logic_plan = logic_plan
        self.context.backlog = backlog

        # Publish event for UI Kanban initialization
        self.context.event_publisher.publish(
            "agent_board_update",
            action="init_backlog",
            tasks=backlog
        )

        self.context.event_publisher.publish(
            "phase_complete",
            phase="2.5",
            message=f"Logic plan and Backlog ({len(backlog)} tasks) created",
        )
        self.context.logger.info(
            f"[PROJECT_NAME:{project_name}] PHASE 2.5 complete: Plans and Backlog created."
        )

        return generated_files, initial_structure, file_paths

    async def _generate_backlog(
        self, project_description: str, readme_content: str, initial_structure: Dict
    ) -> List[Dict]:
        """Generates a list of micro-tasks from project context with retries and robust parsing."""
        from backend.utils.core.llm.llm_response_parser import LLMResponseParser

        system_prompt, user_prompt = AutoGenPrompts.agile_backlog_planning(
            project_description=project_description,
            initial_structure=json.dumps(initial_structure, indent=2),
            readme_content=readme_content[:2000]
        )

        attempts = 0
        max_attempts = 3
        last_error = ""

        while attempts < max_attempts:
            attempts += 1
            try:
                current_user_prompt = user_prompt
                if last_error:
                    current_user_prompt += f"\n\nRETRY DUE TO PREVIOUS ERROR:\n{last_error}\nPlease fix the JSON format. Ensure it is a valid JSON array of objects."

                response_data, _ = self.context.llm_manager.get_client("planner").chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": current_user_prompt},
                    ],
                    tools=[],
                    options_override={"temperature": 0.2},
                )

                response_text = response_data.get("content", "")
                
                # Use robust parser
                backlog = LLMResponseParser.extract_json(response_text)
                
                if not backlog:
                    import re
                    # Try to extract from tags specifically
                    tag_match = re.search(r"<backlog_json>([\s\S]*?)(?:</backlog_json>|$)", response_text, re.IGNORECASE)
                    if tag_match:
                        backlog = LLMResponseParser.extract_json(tag_match.group(1))

                if isinstance(backlog, list):
                    return backlog
                else:
                    # Log failed response for debugging
                    import uuid
                    fail_id = uuid.uuid4().hex[:6]
                    fail_log = self.context.generated_projects_dir / f"FAILED_BACKLOG_{fail_id}_ATTEMPT_{attempts}.txt"
                    self.context.file_manager.write_file(fail_log, response_text)
                    raise ValueError(f"Response is not a JSON list. Raw response saved to {fail_log.name}")

            except Exception as e:
                last_error = str(e)
                self.context.logger.warning(f"  ⚠ Attempt {attempts} failed to generate backlog: {e}")
                if attempts == max_attempts:
                    self.context.logger.error("  ✖ Backlog generation failed after max attempts. Using fallback.")
                    return self._create_fallback_backlog(initial_structure)

        return self._create_fallback_backlog(initial_structure)

    def _create_fallback_backlog(self, initial_structure: Dict) -> List[Dict]:
        """Creates a basic backlog based on file structure if LLM fails."""
        backlog = []
        # Flatten structure to get file paths
        def get_files(struct, prefix=""):
            files = []
            for name, content in struct.items():
                path = f"{prefix}/{name}" if prefix else name
                if isinstance(content, dict) and content.get("type") == "file":
                    files.append(path)
                elif isinstance(content, dict):
                    files.extend(get_files(content, path))
            return files

        files = get_files(initial_structure)
        for i, file_path in enumerate(files):
            backlog.append({
                "id": f"TASK-{i+1:03d}",
                "title": f"Implement {file_path}",
                "description": f"Create the content for {file_path}",
                "file_path": file_path,
                "task_type": "create_file",
                "dependencies": [],
                "context_files": []
            })
        return backlog

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
        already_planned_contracts: Dict[str, List[str]] = None,
    ) -> Dict[str, Dict]:
        """Create detailed plans for files in a category with robust parsing."""
        from backend.utils.core.llm.llm_response_parser import LLMResponseParser

        files_list = "\n".join(f"- {f}" for f in files)

        # Serialize already-planned contracts for the prompt (Fix 2)
        contracts_text = ""
        if already_planned_contracts:
            lines = []
            for fp, exports in already_planned_contracts.items():
                exports_str = ", ".join(exports) if exports else "(none)"
                lines.append(f"  {fp}: exports [{exports_str}]")
            contracts_text = "\n".join(lines)

        system_prompt, user_prompt = AutoGenPrompts.architecture_planning_detailed(
            category=category,
            files_list=files_list,
            project_description=project_description,
            already_planned_contracts=contracts_text,
        )

        attempts = 0
        max_attempts = 3
        last_error = ""

        while attempts < max_attempts:
            attempts += 1
            try:
                current_user_prompt = user_prompt
                if last_error:
                    current_user_prompt += f"\n\nRETRY DUE TO PREVIOUS ERROR:\n{last_error}\nPlease ensure your output is a valid JSON object."

                response_data, _ = self.context.llm_manager.get_client("planner").chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": current_user_prompt},
                    ],
                    tools=[],
                    options_override={"temperature": 0.3},
                )

                response_text = response_data.get("content", "")

                plans = LLMResponseParser.extract_json(response_text)
                
                if not plans:
                    import re
                    tag_match = re.search(r"<plan_json>([\s\S]*?)(?:</plan_json>|$)", response_text, re.IGNORECASE)
                    if tag_match:
                        plans = LLMResponseParser.extract_json(tag_match.group(1))

                if isinstance(plans, dict) and any(f in plans for f in files):
                    return plans
                else:
                    # Log failed response for debugging
                    fail_log = self.context.generated_projects_dir / f"FAILED_PLAN_{category}_{attempts}.txt"
                    self.context.file_manager.write_file(fail_log, response_text)
                    raise ValueError(f"LLM returned invalid planning JSON. Raw response saved to {fail_log.name}")

            except Exception as e:
                last_error = str(e)
                self.context.logger.warning(f"  ⚠ Attempt {attempts} failed to plan category {category}: {e}")
                if attempts == max_attempts:
                    self.context.logger.error(f"  ✖ Planning for category {category} failed after max attempts. Using basic plans.")
                    return self._create_basic_plans(files, category, project_description)

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
