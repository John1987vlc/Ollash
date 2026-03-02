"""Logic Planning Phase - Creates detailed implementation plans for each file."""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.utils.domains.auto_generation.prompt_templates import AutoGenPrompts


class LogicPlanningPhase(BasePhase):
    """
    Phase 2.5 (between Structure and FileContentGeneration):
    Creates a detailed implementation plan for each file, specifying:
    - What the file should do
    - Key functions/classes to implement
    - Dependencies and interactions
    - Validation criteria

    This plan is then used by FileContentGenerationPhase to generate accurate content.
    """

    phase_id = "2.5"
    phase_label = "Logic Planning"

    async def run(
        self,
        project_description: str,
        project_name: str,
        project_root: Path,
        readme_content: str,
        initial_structure: Dict[str, Any],
        generated_files: Dict[str, str],
        file_paths: List[str],
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        self.context.logger.info(
            f"[PROJECT_NAME:{project_name}] PHASE 2.5: Creating detailed logic plans for {len(file_paths)} files..."
        )

        logic_plan = {}

        # Group files by type/purpose
        files_by_category = self._categorize_files(file_paths)

        # Accumulate exports from already-planned categories so later categories
        # can see the API contracts and stay consistent (Fix 2)
        already_planned_contracts: Dict[str, List[str]] = {}

        for category, files in files_by_category.items():
            # Nano tier: cap at 5 files/category to avoid overwhelming small models
            _max_files = 5 if self.context._is_small_model() else 15
            files_to_plan = files[:_max_files]
            self.context.logger.info(f"  Planning {category}: {len(files_to_plan)} files (limited from {len(files)})")

            # Generate a plan for this category, passing already-planned contracts
            category_plan = await self._plan_category(
                category,
                files_to_plan,
                project_description,
                readme_content,
                initial_structure,
                already_planned_contracts,
            )

            for file_path, plan in category_plan.items():
                logic_plan[file_path] = plan
                # Register this file's exports so subsequent categories see them
                already_planned_contracts[file_path] = plan.get("exports", [])

        # Save plan to disk
        plan_file = project_root / "IMPLEMENTATION_PLAN.json"
        self.context.file_manager.write_file(plan_file, json.dumps(logic_plan, indent=2))
        generated_files["IMPLEMENTATION_PLAN.json"] = json.dumps(logic_plan, indent=2)

        # NEW: Generate Agile Backlog (Opt 4: incremental mode for small models)
        self.context.logger.info("  Generating Agile Backlog of micro-tasks...")
        if self.context._opt_enabled("opt4_incremental_backlog"):
            backlog = await self._generate_backlog_incrementally(project_description, readme_content, initial_structure)
        else:
            backlog = await self._generate_backlog(project_description, readme_content, initial_structure)

        backlog_file = project_root / "BACKLOG.json"
        self.context.file_manager.write_file(backlog_file, json.dumps(backlog, indent=2))
        generated_files["BACKLOG.json"] = json.dumps(backlog, indent=2)

        # Store in context for FileContentGenerationPhase to use
        self.context.logic_plan = logic_plan
        self.context.backlog = backlog

        # Publish event for UI Kanban initialization
        self.context.event_publisher.publish("agent_board_update", action="init_backlog", tasks=backlog)

        self.context.logger.info(
            f"[PROJECT_NAME:{project_name}] PHASE 2.5: Logic plan and Backlog ({len(backlog)} tasks) created."
        )

        return generated_files, initial_structure, file_paths

    async def _generate_backlog_incrementally(
        self,
        project_description: str,
        readme_content: str,
        initial_structure: Dict,
        max_tasks: int = 30,
    ) -> List[Dict]:
        """Generate the Agile backlog ONE micro-task at a time (Opt 4).

        Instead of asking the model for the full backlog in one shot (which overloads
        3B models), this method iteratively asks for the NEXT task based on what has
        been generated so far. The Blackboard / DecisionBlackboard is used as
        short-term memory between iterations.

        Falls back to :meth:`_generate_backlog` if zero tasks are produced.

        Args:
            project_description: High-level project description.
            readme_content: README context (truncated).
            initial_structure: Project file tree dict.
            max_tasks: Hard ceiling to prevent infinite loops (default 30).

        Returns:
            List of micro-task dicts, each with ``id``, ``title``, ``file_path``,
            ``task_type``, and ``dependencies``.
        """
        from backend.utils.core.llm.llm_response_parser import LLMResponseParser
        from backend.utils.domains.auto_generation.prompt_templates import AutoGenPrompts

        backlog: List[Dict] = []
        structure_str = json.dumps(initial_structure, indent=2)

        self.context.logger.info("  [Opt4] Using incremental backlog generation...")

        while len(backlog) < max_tasks:
            system_prompt, user_prompt = AutoGenPrompts.next_backlog_task(
                project_description=project_description,
                initial_structure=structure_str,
                backlog_so_far=backlog,
            )
            try:
                response_data, _ = self.context.llm_manager.get_client("planner").chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    tools=[],
                    options_override={"temperature": 0.1},
                )
                response_text = response_data.get("content", "")

                # Extract task from <task_json>...</task_json>
                import re as _re

                tag_match = _re.search(r"<task_json>([\s\S]*?)(?:</task_json>|$)", response_text, _re.IGNORECASE)
                raw = tag_match.group(1).strip() if tag_match else response_text
                task_data = LLMResponseParser.extract_json(raw)

                if not isinstance(task_data, dict):
                    self.context.logger.info("  [Opt4] Unexpected response type — stopping incremental loop.")
                    break

                # Completion signal
                if task_data.get("complete"):
                    self.context.logger.info(f"  [Opt4] Model signalled completion after {len(backlog)} tasks.")
                    break

                file_path = task_data.get("file_path", "")
                if not file_path:
                    self.context.logger.info("  [Opt4] Task missing file_path — skipping.")
                    continue

                # Auto-assign ID if missing
                if "id" not in task_data:
                    task_data["id"] = f"TASK-{len(backlog) + 1:03d}"

                backlog.append(task_data)

                # Record decision for cross-phase memory
                try:
                    self.context.decision_blackboard.record_decision(
                        key=f"backlog_task_{task_data['id']}",
                        value=json.dumps(task_data),
                        context=f"Incremental backlog task {task_data['id']}",
                    )
                except Exception:
                    pass

                self.context.logger.info(f"  [Opt4] Task {task_data['id']}: {task_data.get('title', file_path)}")

            except Exception as exc:
                self.context.logger.warning(f"  [Opt4] Incremental step failed: {exc}")
                break

        if not backlog:
            self.context.logger.info("  [Opt4] No tasks produced incrementally — falling back to batch generation.")
            return await self._generate_backlog(project_description, readme_content, initial_structure)

        self.context.logger.info(f"  [Opt4] Incremental backlog complete: {len(backlog)} tasks.")
        return backlog

    async def _generate_backlog(
        self, project_description: str, readme_content: str, initial_structure: Dict
    ) -> List[Dict]:
        """Generates a list of micro-tasks from project context with retries and robust parsing."""
        from backend.utils.core.llm.llm_response_parser import LLMResponseParser

        system_prompt, user_prompt = AutoGenPrompts.agile_backlog_planning(
            project_description=project_description,
            initial_structure=json.dumps(initial_structure, indent=2),
            readme_content=readme_content[:2000],
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
                    tag_match = re.search(
                        r"<backlog_json>([\s\S]*?)(?:</backlog_json>|$)", response_text, re.IGNORECASE
                    )
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
            backlog.append(
                {
                    "id": f"TASK-{i + 1:03d}",
                    "title": f"Implement {file_path}",
                    "description": f"Create the content for {file_path}",
                    "file_path": file_path,
                    "task_type": "create_file",
                    "dependencies": [],
                    "context_files": [],
                }
            )
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

                if not response_text.strip():
                    self.context.logger.warning(
                        f"  ⚠ LLM returned empty response for category {category} (Attempt {attempts})"
                    )
                    continue

                plans = LLMResponseParser.extract_json(response_text)

                if not plans:
                    # Intento desesperado: si no hay tags, buscar cualquier objeto JSON
                    plans = LLMResponseParser.extract_json(response_text)

                if isinstance(plans, dict) and (not files or any(f in plans for f in files)):
                    return plans
                else:
                    # Log failed response for debugging
                    fail_log = self.context.generated_projects_dir / f"FAILED_PLAN_{category}_{attempts}.txt"
                    log_content = f"--- RAW RESPONSE ---\n{response_text}\n--- END RAW ---"
                    self.context.file_manager.write_file(fail_log, log_content)
                    raise ValueError(
                        f"LLM returned invalid planning JSON for {category}. Raw response saved to {fail_log.name}"
                    )

            except Exception as e:
                last_error = str(e)
                self.context.logger.warning(f"  ⚠ Attempt {attempts} failed to plan category {category}: {e}")
                if attempts == max_attempts:
                    self.context.logger.error(
                        f"  ✖ Planning for category {category} failed after max attempts. Using basic plans."
                    )
                    return self._create_basic_plans(files, category, project_description)

        return self._create_basic_plans(files, category, project_description)

    def _create_basic_plans(self, files: List[str], category: str, project_description: str) -> Dict[str, Dict]:
        """Create basic fallback plans anchored to the original project description."""
        plans = {}

        # Validation: If project_description is too short, we might be losing intent
        if len(project_description) < 10:
            self.context.logger.warning("Project description is critically short for fallback planning.")

        for file_path in files:
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
