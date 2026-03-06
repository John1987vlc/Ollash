"""Logic Planning Phase - Creates detailed implementation plans for each file."""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from pydantic import ValidationError

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.utils.domains.auto_generation.prompt_templates import AutoGenPrompts
from backend.core.config_schemas import LogicPlanningOutput


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

        # F29: Use Pydantic-validated unified planning for better consistency
        logic_plan = {}
        backlog = []

        # F31: For nano models, be extremely aggressive with limits
        is_nano = bool(self.context._is_small_model())
        
        # Select key files for planning - limit more for nano
        planning_files = [f for f in file_paths if "src/" in f or "app/" in f or "main" in f.lower()]
        if is_nano:
            planning_files = planning_files[:5] if planning_files else file_paths[:5]
            self.context.logger.info(f"  [Nano] Limiting planning to {len(planning_files)} core files.")
        else:
            planning_files = planning_files[:15] if planning_files else file_paths[:10]

        # Fix 1: Detect module system early so we can inject the hint into the LLM prompt
        self._detect_module_system(file_paths, project_root)
        _ms = getattr(self.context, "module_system", "")
        if _ms == "esm":
            _module_system_hint = "All JS/TS files MUST use ESM (import/export) syntax — never use require()."
        elif _ms == "cjs":
            _module_system_hint = (
                "All JS/TS files MUST use CommonJS (require/module.exports) syntax — never use import/export."
            )
        else:
            _module_system_hint = ""

        # F31: If nano, we might prefer incremental or simplified planning to avoid hangs
        if is_nano:
            self.context.logger.info("  [Nano] Using deterministic backlog and basic planning to prevent hangs.")
            logic_plan, backlog = await self._create_deterministic_backlog(
                file_paths, project_description, initial_structure
            )
        else:
            system_prompt, user_prompt = await AutoGenPrompts.logic_planning(
                project_description,
                json.dumps(initial_structure, indent=2),
                planning_files,
                module_system_hint=_module_system_hint,
            )

            max_retries = 3
            last_error = ""

            for attempt in range(1, max_retries + 1):
                try:
                    current_user_prompt = user_prompt
                    if last_error:
                        current_user_prompt += f"\n\nCRITICAL: Previous output failed validation:\n{last_error}\n\nPlease fix the JSON structure and ensure all required fields are present."

                    response_data, _ = self.context.llm_manager.get_client("planner").chat(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": current_user_prompt},
                        ],
                        options_override={"temperature": 0.2},
                    )

                    raw_content = response_data.get("content", "")
                    parsed_json = self.context.response_parser.extract_json(raw_content)

                    if parsed_json is None:
                        raise ValueError("Could not extract valid JSON from planner response.")

                    # Fix: If the LLM returned a list directly (common error), it's likely the backlog
                    if isinstance(parsed_json, list):
                        self.context.logger.info("  ⚠ Planner returned a list instead of a dict. Interpreting as backlog.")
                        backlog = parsed_json
                        # Generate basic plans for the files in the backlog
                        logic_plan = self._create_basic_plans(
                            [t.get("file_path") for t in backlog if t.get("file_path")], "general", project_description
                        )
                        break

                    # Pydantic Validation (The "Hardening")
                    validated_output = LogicPlanningOutput.model_validate(parsed_json)

                    # Convert back to dict for context storage
                    logic_plan = {k: v.model_dump() for k, v in validated_output.logic_plan.items()}
                    backlog = [t.model_dump() for t in validated_output.backlog]

                    self.context.logger.info(f"  ✓ Logic planning and backlog validated on attempt {attempt}")
                    break

                except (ValidationError, ValueError, Exception) as e:
                    last_error = str(e)
                    self.context.logger.warning(f"  ⚠ Logic planning attempt {attempt} failed validation: {last_error}")
                    if attempt == max_retries:
                        self.context.logger.error(
                            "  ✖ Logic planning failed after max retries. Using legacy categorization fallback."
                        )
                        # Legacy fallback logic
                        logic_plan, backlog = await self._legacy_planning_fallback(
                            file_paths, project_description, readme_content, initial_structure
                        )

        # F31: Persist tasks to Blackboard for deterministic execution
        if hasattr(self.context, "decision_blackboard"):
            for t in backlog:
                self.context.decision_blackboard.record_task(
                    task_id=t.get("id", ""),
                    title=t.get("title", ""),
                    description=t.get("description", ""),
                    file_path=t.get("file_path", ""),
                    task_type=t.get("task_type", "create_file"),
                    dependencies=t.get("dependencies", []),
                )

        # Save plans to disk
        plan_file = project_root / "IMPLEMENTATION_PLAN.json"
        self.context.file_manager.write_file(plan_file, json.dumps(logic_plan, indent=2))
        generated_files["IMPLEMENTATION_PLAN.json"] = json.dumps(logic_plan, indent=2)

        backlog_file = project_root / "BACKLOG.json"
        self.context.file_manager.write_file(backlog_file, json.dumps(backlog, indent=2))
        generated_files["BACKLOG.json"] = json.dumps(backlog, indent=2)

        # F6: Serialize backlog to Kanban tasks.json
        import datetime as _dt

        tasks_kanban = {
            "version": "1.0",
            "project": project_name,
            "created_at": _dt.datetime.now().isoformat(),
            "columns": {
                "todo": [
                    {
                        "id": t.get("id", f"TASK-{i + 1:03d}"),
                        "title": t.get("title", t.get("file_path", "")),
                        "description": t.get("description", ""),
                        "file_path": t.get("file_path", ""),
                        "task_type": t.get("task_type", "create_file"),
                        "dependencies": t.get("dependencies", []),
                        "assignee": "agent",
                        "status": "todo",
                    }
                    for i, t in enumerate(backlog)
                ],
                "in_progress": [],
                "done": [],
            },
        }
        tasks_json = json.dumps(tasks_kanban, indent=2)
        tasks_file = project_root / "tasks.json"
        self.context.file_manager.write_file(tasks_file, tasks_json)
        generated_files["tasks.json"] = tasks_json

        # Store in context for FileContentGenerationPhase to use
        self.context.logic_plan = logic_plan
        self.context.backlog = backlog

        # Publish event for UI Kanban initialization
        await self.context.event_publisher.publish("agent_board_update", action="init_backlog", tasks=backlog)

        self.context.logger.info(
            f"[PROJECT_NAME:{project_name}] PHASE 2.5: Logic plan and Backlog ({len(backlog)} tasks) created."
        )

        return generated_files, initial_structure, file_paths

    async def _create_deterministic_backlog(
        self, file_paths: List[str], project_description: str, initial_structure: Dict
    ) -> Tuple[Dict[str, Any], List[Dict]]:
        """Creates a 100% deterministic backlog by mapping every file path to a task."""
        self.context.logger.info(f"  [Deterministic] Creating tasks for all {len(file_paths)} files.")

        # F31: Nano tier - skip README.md if it already exists from Phase 1
        is_nano = bool(self.context._is_small_model())
        if is_nano:
            file_paths = [p for p in file_paths if p != "README.md"]
            self.context.logger.info(f"  [Nano] Filtered out README.md from backlog (already generated).")

        logic_plan = self._create_basic_plans(file_paths, "all", project_description)
        backlog = []
        for i, path in enumerate(file_paths):
            task_id = f"TASK-{i + 1:03d}"
            # Advanced dependency detection for tests
            deps = []
            if "test" in path.lower():
                p = Path(path)
                # Patterns: test_main.py -> main.py, app.test.js -> app.js
                stem = p.stem.replace("test_", "").replace("_test", "").replace(".test", "")
                ext = p.suffix
                
                # Search for the source file in the same directory or in src/
                potential_names = [f"{stem}{ext}", f"src/{stem}{ext}", f"app/{stem}{ext}"]
                for pot in potential_names:
                    if pot in file_paths and pot != path:
                        deps.append(pot)
                        break

            backlog.append({
                "id": task_id,
                "title": f"Implement {path}",
                "description": f"Create content for {path} as defined in project requirements.",
                "file_path": path,
                "task_type": "create_file",
                "dependencies": deps,
            })
            
        return logic_plan, backlog

    def _detect_module_system(self, file_paths: List[str], project_root: Path) -> None:
        """Detect and store the JS module system (ESM or CJS) for this project.

        Priority order:
        1. ``package.json`` ``"type": "module"`` → ESM
        2. Modern framework detected via tech_stack_info (React, Next.js, Vite, Nuxt) → ESM
        3. Any ``.mjs`` file in the project → ESM
        4. Default → CJS (safer for Node.js backends without a declared type)

        Result is stored on ``context.module_system`` and persisted to
        ``context.decision_blackboard`` so later phases can read it.
        """
        js_files = [f for f in file_paths if Path(f).suffix.lower() in (".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs")]
        if not js_files:
            # Not a JS/TS project — leave module_system blank
            return

        module_system = "cjs"  # default

        # 1. Check package.json "type" field
        pkg_path = project_root / "package.json"
        if pkg_path.exists():
            try:
                import json as _json

                pkg = _json.loads(pkg_path.read_text(encoding="utf-8"))
                if pkg.get("type") == "module":
                    module_system = "esm"
            except Exception:
                pass

        # 2. Modern framework implies ESM
        if module_system == "cjs":
            tech = getattr(self.context, "tech_stack_info", None)
            if tech is not None:
                framework = (getattr(tech, "framework", "") or "").lower()
                if any(f in framework for f in ("react", "next", "vite", "nuxt", "svelte", "angular")):
                    module_system = "esm"

        # 3. Any .mjs file → ESM
        if module_system == "cjs" and any(Path(f).suffix.lower() == ".mjs" for f in js_files):
            module_system = "esm"

        self.context.module_system = module_system
        try:
            self.context.decision_blackboard.store("module_system", module_system)
        except Exception:
            pass
        self.context.logger.info(f"  [Fix1] Module system decided: {module_system.upper()}")

    async def _legacy_planning_fallback(self, file_paths, project_description, readme_content, initial_structure):
        """Original categorized planning logic as a safe fallback."""
        logic_plan = {}
        
        # F31: For nano tier, we skip LLM planning entirely to avoid hangs and repetitions
        if bool(self.context._is_small_model()):
            self.context.logger.info("  [Nano] Using direct file-to-task mapping for reliability.")
            logic_plan = self._create_basic_plans(file_paths, "all", project_description)
            backlog = self._create_fallback_backlog(initial_structure)
            return logic_plan, backlog

        files_by_category = self._categorize_files(file_paths)
        already_planned_contracts = {}

        for category, files in files_by_category.items():
            _max_files = 15
            files_to_plan = files[:_max_files]
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
                already_planned_contracts[file_path] = plan.get("exports", [])

        # Incremental backlog fallback
        if self.context._opt_enabled("opt4_incremental_backlog"):
            backlog = await self._generate_backlog_incrementally(project_description, readme_content, initial_structure)
        else:
            backlog = await self._generate_backlog(project_description, readme_content, initial_structure)

        return logic_plan, backlog

    async def _generate_backlog_incrementally(
        self,
        project_description: str,
        readme_content: str,
        initial_structure: Dict,
        max_tasks: int = 30,
    ) -> List[Dict]:
        """Generate the Agile backlog ONE micro-task at a time (Opt 4)."""
        from backend.utils.core.llm.llm_response_parser import LLMResponseParser
        from backend.utils.domains.auto_generation.prompt_templates import AutoGenPrompts

        backlog: List[Dict] = []
        structure_str = json.dumps(initial_structure, indent=2)

        self.context.logger.info(f"  [Opt4] Generating backlog incrementally (limit: {max_tasks})...")

        while len(backlog) < max_tasks:
            system_prompt, user_prompt = await AutoGenPrompts.next_backlog_task(
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
                self.context.logger.info(f"  [Opt4] Task {task_data['id']}: {task_data.get('title', file_path)}")
                try:
                    self.context.decision_blackboard.record_decision(
                        f"task_{task_data['id']}", task_data.get("file_path", ""), "incremental_backlog"
                    )
                except Exception:
                    pass

            except Exception as exc:
                self.context.logger.warning(f"  [Opt4] Incremental step failed: {exc}")
                break

        if not backlog:
            return await self._generate_backlog(project_description, readme_content, initial_structure)

        return backlog

    async def _generate_backlog(
        self, project_description: str, readme_content: str, initial_structure: Dict
    ) -> List[Dict]:
        """Generates a list of micro-tasks from project context with retries and robust parsing."""
        from backend.utils.core.llm.llm_response_parser import LLMResponseParser

        system_prompt, user_prompt = await AutoGenPrompts.agile_backlog_planning(
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
                    current_user_prompt += (
                        f"\n\nRETRY DUE TO PREVIOUS ERROR:\n{last_error}\nPlease fix the JSON format."
                    )

                response_data, _ = self.context.llm_manager.get_client("planner").chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": current_user_prompt},
                    ],
                    tools=[],
                    options_override={"temperature": 0.2},
                )

                response_text = response_data.get("content", "")
                backlog = LLMResponseParser.extract_json(response_text)

                if isinstance(backlog, list):
                    return backlog
                raise ValueError("Response is not a JSON list.")

            except Exception as e:
                last_error = str(e)
                self.context.logger.warning(f"  ⚠ Attempt {attempts} failed to generate backlog: {e}")
                if attempts == max_attempts:
                    return self._create_fallback_backlog(initial_structure)

        return self._create_fallback_backlog(initial_structure)

    def _create_fallback_backlog(self, initial_structure: Dict) -> List[Dict]:
        """Creates a basic backlog based on file structure if LLM fails."""
        backlog = []

        # Simple heuristic to extract files from initial_structure
        def extract_files(node, current_path=""):
            files = []
            for file_name in node.get("files", []):
                files.append(str(Path(current_path) / file_name).replace("\\", "/"))
            for folder in node.get("folders", []):
                folder_name = folder.get("name")
                if folder_name:
                    files.extend(extract_files(folder, str(Path(current_path) / folder_name)))
            return files

        files = extract_files(initial_structure)
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

    def _create_basic_plans(self, file_paths: List[str], category: str, project_description: str) -> Dict[str, Any]:
        """Create minimal per-file plans from project description without an LLM call.

        Used as a unit-testable fallback when the main planning loop fails and as
        a helper by ``_legacy_planning_fallback``.
        """
        plans: Dict[str, Any] = {}
        for file_path in file_paths:
            file_stem = Path(file_path).stem
            plans[file_path] = {
                "purpose": f"Implement {file_stem} module for {project_description}",
                "main_logic": [f"Implement core logic for {project_description} in {file_stem}"],
                "exports": [file_stem],
                "dependencies": [],
                "validation_criteria": [f"{file_stem} functions correctly"],
            }
        return plans

    def _categorize_files(self, file_paths: List[str]) -> Dict[str, List[str]]:
        """Group files by their category."""
        categories = {"config": [], "main": [], "utils": [], "tests": [], "web": [], "other": []}
        for file_path in file_paths:
            if any(x in file_path for x in ["config", "settings", "env"]):
                categories["config"].append(file_path)
            elif any(x in file_path for x in ["test", "spec"]):
                categories["tests"].append(file_path)
            elif any(x in file_path for x in ["utils", "helper", "lib"]):
                categories["utils"].append(file_path)
            elif any(x in file_path for x in [".html", ".css", ".js", "web"]):
                categories["web"].append(file_path)
            elif any(x in file_path for x in ["main", "app", "server", "index"]):
                categories["main"].append(file_path)
            else:
                categories["other"].append(file_path)
        return {k: v for k, v in categories.items() if v}

    async def _plan_category(
        self, category, files, project_description, readme_content, initial_structure, already_planned_contracts
    ):
        """Legacy categorized planning."""
        from backend.utils.core.llm.llm_response_parser import LLMResponseParser

        system_prompt, user_prompt = await AutoGenPrompts.architecture_planning_detailed(
            category=category,
            files_list="\n".join(f"- {f}" for f in files),
            project_description=project_description,
            already_planned_contracts=str(already_planned_contracts),
        )
        response_data, _ = self.context.llm_manager.get_client("planner").chat(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            options_override={"temperature": 0.3},
        )
        return LLMResponseParser.extract_json(response_data.get("content", "")) or {}
