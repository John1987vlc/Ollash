from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.utils.domains.auto_generation.prompt_templates import AutoGenPrompts
from backend.utils.core.analysis.context_distiller import ContextDistiller


class FileContentGenerationPhase(BasePhase):
    """
    Phase 4: Generates the content for all planned files, potentially in parallel.
    NOW USES LOGIC PLANS for more accurate, complete implementations.
    Handles dependency awareness, incremental validation, and error logging.
    """

    phase_id = "4"
    phase_label = "File Content Generation"

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
            f"[PROJECT_NAME:{project_name}] PHASE 4: Executing Agile Backlog with Self-Reflection..."
        )

        # F3: Build API map once for token-efficient context on small models
        if generated_files:
            self.context.build_api_map(generated_files)
        
        is_nano = self.context._is_small_model()
        _use_signatures = is_nano or self.context._is_small_model("coder")

        await self.context.event_publisher.publish("phase_start", phase="4", message="Starting agile backlog execution")

        backlog = getattr(self.context, "backlog", [])
        if not backlog and hasattr(self.context, "logic_plan"):
            for i, (path, plan) in enumerate(self.context.logic_plan.items()):
                backlog.append(
                    {
                        "id": f"TASK-{i:03d}",
                        "title": f"Implement {path}",
                        "description": plan.get("purpose", f"Generate {path}"),
                        "file_path": path,
                        "task_type": "create_file",
                        "dependencies": [],
                        "context_files": [],
                    }
                )

        # Sort backlog respecting declared dependencies (Fix 3)
        backlog = self._topological_sort(backlog)

        # Nano tier: pre-expand implement_function tasks into per-function sub-tasks
        if is_nano:
            from backend.agents.auto_agent_phases.nano_task_expander import NanoTaskExpander

            expanded_backlog: List[Dict[str, Any]] = []
            for _task in backlog:
                _tp = _task.get("task_type", "")
                _fp = str(_task.get("file_path", ""))
                if _tp == "implement_function":
                    _sub = NanoTaskExpander.expand(_task, generated_files.get(_fp, ""))
                    if _sub:
                        expanded_backlog.extend(_sub)
                        self.context.logger.info(f"  [NanoExpander] '{_fp}' → {len(_sub)} per-function nano-tasks")
                        continue
                expanded_backlog.append(_task)
            # Re-sort after expansion so new sub-task deps are respected
            backlog = self._topological_sort(expanded_backlog)

        total_tasks = len(backlog)
        completed_tasks = 0
        completed_task_ids: List[str] = []  # Mejora 3: track completed IDs for progress injection

        for task in backlog:
            task_id = task.get("id", "UNKNOWN")
            title = task.get("title", "Untitled")

            # F29: Ensure file_path is a string (handle cases where LLM might provide a list)
            raw_file_path = task.get("file_path", "")
            if isinstance(raw_file_path, list) and raw_file_path:
                file_path = str(raw_file_path[0])
            else:
                file_path = str(raw_file_path)

            task_type = task.get("task_type", "create_file")

            completed_tasks += 1
            self.context.logger.info(f"  [Task {completed_tasks}/{total_tasks}] {task_id}: {title}")

            # CRITICAL: Binary Guard - Skip LLM call for binary files
            if self._is_binary_file(file_path):
                self.context.logger.info(f"    Skipped: Binary file detected ({file_path})")
                generated_files[file_path] = ""
                # Move to done in Kanban anyway
                await self.context.event_publisher.publish(
                    "agent_board_update", action="move_task", task_id=task_id, new_status="done"
                )
                continue

            # Extension guard: skip files whose extension is not allowed for the detected project type
            _ptype = getattr(self.context, "project_type_info", None)
            if _ptype and _ptype.project_type != "unknown" and _ptype.confidence >= 0.10:
                from pathlib import Path as _Path

                _suffix = _Path(file_path).suffix.lower()
                if _suffix and _suffix not in _ptype.allowed_extensions:
                    self.context.logger.warning(
                        f"    [ExtensionGuard] Skipped '{file_path}': "
                        f"extension '{_suffix}' not allowed for "
                        f"project type '{_ptype.project_type}'"
                    )
                    generated_files[file_path] = ""
                    await self.context.event_publisher.publish(
                        "agent_board_update",
                        action="move_task",
                        task_id=task_id,
                        new_status="skipped_extension",
                    )
                    continue

            # Notify progress to Kanban Board
            await self.context.event_publisher.publish(
                "agent_board_update", action="move_task", task_id=task_id, new_status="in_progress"
            )

            try:
                # 1. Prepare context + build prompts
                ctx_data = await self._prepare_task_context(
                    task=task,
                    file_path=file_path,
                    task_type=task_type,
                    generated_files=generated_files,
                    readme_content=readme_content,
                    project_name=project_name,
                    _use_signatures=_use_signatures,
                    is_nano=is_nano,
                )
                context_files_content = ctx_data["context_files_content"]

                system_prompt, user_prompt = await AutoGenPrompts.micro_task_execution(
                    title=title,
                    description=task.get("description", ""),
                    file_path=file_path,
                    task_type=task_type,
                    readme_content=readme_content[:1000],
                    context_files_content=context_files_content[:4000],
                    logic_plan_section=ctx_data["logic_plan_section"],
                    allowed_actions=ctx_data["allowed_actions"],
                    anti_pattern_warnings=ctx_data["anti_pattern_warnings"],
                    few_shot_section=ctx_data["few_shot_section"],
                )

                content = ""
                attempts = 0
                max_attempts = 2 if is_nano else 3 # F31: Reduce retries for nano to fail fast
                last_error = ""

                # 3. Self-Reflection and Correction Loop
                while attempts < max_attempts:
                    attempts += 1
                    current_user_prompt = user_prompt

                    if last_error:
                        # Implement Chain of Thought (CoT) for retries
                        is_code = file_path.endswith((".js", ".jsx", ".ts", ".tsx", ".py", ".java", ".go", ".rs"))
                        cot_instruction = ""
                        if is_code:
                            cot_instruction = (
                                "\n\nCRITICAL: You previously generated code that failed validation. "
                                "First, explain WHY the previous logic failed (in a <reflection> tag), "
                                "then provide the corrected implementation in <code_created>."
                            )

                        current_user_prompt += f"\n\nRETRY DUE TO PREVIOUS ERROR:\n{last_error}{cot_instruction}"

                    # 3. LLM Call — use nano_coder role for ≤8B models
                    _coder_role = "nano_coder" if is_nano else "coder"
                    response_data, _ = self.context.llm_manager.get_client(_coder_role).chat(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": current_user_prompt},
                        ],
                        tools=[],
                        options_override={"temperature": 0.1},
                    )

                    raw_response = response_data.get("content", "").strip()

                    # 4. XML Extraction via Regex (Case-insensitive and robust to whitespace)
                    import re
                    from backend.utils.core.llm.llm_response_parser import LLMResponseParser

                    codigo_match = re.search(
                        r"<code_created>([\s\S]*?)(?:</code_created>|$)", raw_response, re.IGNORECASE
                    )

                    if not codigo_match:
                        # FALLBACK: If the model failed tags but used markdown blocks, try to rescue it
                        if "```" in raw_response:
                            # Use language-aware extraction to prefer the block matching the file extension
                            content = LLMResponseParser.extract_code_block_for_file(raw_response, file_path)
                            if content:
                                self.context.logger.info(
                                    f"    ⚠ Attempt {attempts}: Rescued code from markdown block (Missing XML tags)."
                                )
                            else:
                                last_error = (
                                    "FORMAT FAILURE: Missing <code_created> tags and no valid code block found."
                                )
                                self.context.logger.warning(f"    ⚠ Attempt {attempts}: {last_error}")
                                continue
                        else:
                            last_error = "FORMAT FAILURE: You MUST include the <code_created> tag in your response."
                            self.context.logger.warning(f"    ⚠ Attempt {attempts}: Missing XML tags.")
                            continue
                    else:
                        content = codigo_match.group(1).strip()

                    # Radical cleaning: remove any leftover markdown artifacts even if found inside tags
                    content = LLMResponseParser.clean_markdown_artifacts(content)

                    # Fix 3: Ensure HTML files declare UTF-8 charset so suit symbols render correctly
                    if file_path.endswith(".html") and "<meta charset" not in content.lower():
                        content = content.replace("<head>", '<head>\n  <meta charset="UTF-8">', 1)

                    # Opt 6: Active shadow validation — format check + nano repair
                    if self.context._opt_enabled("opt6_active_shadow"):
                        try:
                            lang = self.context.infer_language(file_path)
                            shadow = getattr(self.context, "shadow_evaluator", None)
                            if shadow is not None:
                                content, _ = await shadow.active_shadow_validate(
                                    file_path,
                                    content,
                                    lang,
                                    self.context.llm_manager,
                                    self.context.logger,
                                )
                        except Exception:
                            pass

                    # Feature 1: Critic-Correction Closed Loop
                    # F31: Disable critic loop for nano models to avoid infinite loops/heavy overhead
                    if not is_nano:
                        critic_cfg = getattr(self.context, "config", {})
                        if isinstance(critic_cfg, dict):
                            critic_cfg = critic_cfg.get("critic_loop", {})
                        else:
                            critic_cfg = {}
                        if critic_cfg.get("enabled", True):
                            try:
                                from backend.utils.core.analysis.critic_loop import CriticLoop

                                if not hasattr(self, "_critic_loop"):
                                    self._critic_loop = CriticLoop(self.context.llm_manager, self.context.logger)
                                _lang = self.context.infer_language(file_path)
                                _critic_feedback = await self._critic_loop.review(file_path, content, _lang)
                                if _critic_feedback:
                                    last_error = f"CRITIC FEEDBACK: {_critic_feedback}"
                                    self.context.logger.info(f"    [Critic] Issues in '{file_path}': {_critic_feedback}")
                                    content = ""
                                    continue
                            except Exception:
                                pass  # Critic must never abort generation

                    # Opt 3: Exit Contract — structural validation before syntax check
                    if self.context._opt_enabled("opt3_exit_contract") and task_type:
                        contract_error = self._check_output_contract(file_path, content, task_type)
                        if contract_error:
                            last_error = f"CONTRACT VIOLATION: {contract_error}"
                            self.context.logger.warning(
                                f"    ⚠ Attempt {attempts} contract violation: {contract_error}"
                            )
                            content = ""
                            continue

                    # 5. AST/Syntax Validation
                    validation_result = self.context.files_ctx.validator.validate(file_path, content)

                    # Handle Semantic Warnings (Auto-Heal) - F31: Skip auto-heal for nano
                    if not is_nano and ("logical integrity issues" in validation_result.message or "SEMANTIC WARNING" in str(
                        validation_result
                    )):
                        self.context.logger.info(
                            f"    ⚠ Attempt {attempts}: Integrity issues detected. Attempting auto-heal..."
                        )

                        # Extract the missing requirement from the warning
                        missing_req = "missing function or logic"
                        if "missing" in validation_result.message:
                            missing_req = validation_result.message.split("missing")[-1].strip()

                        # Use CodePatcher to inject
                        from backend.utils.domains.auto_generation.code_patcher import CodePatcher

                        patcher = CodePatcher(
                            self.context.llm_manager.get_client("coder"),
                            self.context.logger,
                            self.context.response_parser,
                        )
                        content = await patcher.inject_missing_function(
                            file_path=file_path,
                            content=content,
                            requirement=missing_req,
                            related_context=context_files_content,
                        )

                        # Re-validate after healing
                        validation_result = self.context.files_ctx.validator.validate(file_path, content)

                    if validation_result.status.name == "VALID":
                        self.context.logger.info(f"    ✓ {file_path} syntactically validated (Attempt {attempts})")
                        break
                    else:
                        last_error = f"SYNTAX ERROR: {validation_result.message}"
                        self.context.logger.warning(
                            f"    ⚠ Attempt {attempts} failed validation: {validation_result.message}"
                        )
                        if attempts < max_attempts:
                            content = ""  # Reset to force retry

                # F2: TDD Agéntico — run a minimal unit test and auto-correct on failure
                if content and file_path.endswith(".py"):
                    content = await self._run_tdd_loop(file_path, content)

                # 6. Final Save and Notification
                if content:
                    await self._save_task_result(
                        file_path=file_path,
                        content=content,
                        task=task,
                        task_id=task_id,
                        title=title,
                        project_root=project_root,
                        generated_files=generated_files,
                        backlog=backlog,
                        completed_task_ids=completed_task_ids,
                        completed_tasks=completed_tasks,
                        total_tasks=total_tasks,
                    )
                else:
                    self.context.logger.error(f"    ✖ Task {task_id} failed after {max_attempts} attempts.")

            except Exception as e:
                self.context.logger.error(f"Fatal error in task {task_id}: {e}")
                # Record error in knowledge base
                self.context.error_knowledge_base.record_error(file_path, "micro_task_failure", str(e), task_id, title)

        self.context.logger.info(
            f"[PROJECT_NAME:{project_name}] PHASE 4: "
            f"Agile execution finished — {completed_tasks}/{total_tasks} tasks completed."
        )

        return generated_files, initial_structure, file_paths

    async def _prepare_task_context(
        self,
        task: Dict[str, Any],
        file_path: str,
        task_type: str,
        generated_files: Dict[str, str],
        readme_content: str,
        project_name: str,
        _use_signatures: bool,
        is_nano: bool = False,
    ) -> Dict[str, Any]:
        """Build the context dict needed to construct prompts for a single task.

        Returns a dict with keys:
        - ``context_files_content``: distilled related-file content
        - ``logic_plan_section``: formatted logic plan for this file
        - ``allowed_actions``: optional allowed-actions string (Opt 1)
        - ``anti_pattern_warnings``: optional warnings string (Opt 5)
        - ``few_shot_section``: optional few-shot examples block
        """
        # 1a. Select related files (prefer predictive pre-fetch, then micro-snapshot, then standard)
        _prefetched = getattr(self.context, "prefetched_context", {})
        if _prefetched and file_path in _prefetched:
            raw_context_files = {file_path: _prefetched[file_path]}
            self.context.logger.info(f"  [PredictiveCtx] Cache hit for '{file_path}'")
        elif not is_nano and self.context._opt_enabled("opt2_micro_context_snapshot"):
            raw_context_files = self.context.build_micro_context_snapshot(file_path)
        else:
            # F31: Force small limit for nano to avoid token overflow
            _max_files = 3 if is_nano else 5
            raw_context_files = self.context.select_related_files(
                file_path, generated_files, signatures_only=_use_signatures, max_files=_max_files
            )
        context_files_content = ContextDistiller.distill_batch(raw_context_files)

        # 1b. Logic plan for this file
        file_logic_plan = getattr(self.context, "logic_plan", {}).get(file_path, {})
        logic_plan_section = self._format_logic_plan_for_prompt(file_logic_plan)

        # Fix 2: Inject DOM contract hint so JS and HTML files share the same element IDs
        _dom_contracts: dict = getattr(self.context, "dom_contracts", {})
        if _dom_contracts:
            _ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
            if _ext in ("js", "ts", "jsx", "tsx"):
                # JS: tell the LLM which IDs it MUST reference
                _all_ids = [_id for ids in _dom_contracts.values() for _id in ids]
                if _all_ids:
                    _ids_str = ", ".join(f'"{i}"' for i in _all_ids)
                    logic_plan_section += (
                        f"\n\n## DOM CONTRACT\n"
                        f"CRITICAL: Use ONLY these element IDs when calling getElementById/querySelector: {_ids_str}\n"
                        f"Do NOT invent new IDs that are not in this list."
                    )
            elif _ext == "html":
                # HTML: tell the LLM which IDs it MUST declare
                _relevant_ids = _dom_contracts.get(file_path, [])
                if not _relevant_ids:
                    _relevant_ids = [_id for ids in _dom_contracts.values() for _id in ids]
                if _relevant_ids:
                    _ids_str = ", ".join(f'id="{i}"' for i in _relevant_ids)
                    logic_plan_section += (
                        f"\n\n## DOM CONTRACT\n"
                        f"CRITICAL: Declare ALL of these element IDs in the HTML: {_ids_str}\n"
                        f"JavaScript files depend on these exact IDs being present."
                    )

        # Opt 1: Allowed-actions block from task_type
        allowed_actions: str | None = None
        if self.context._opt_enabled("opt1_prompt_state_machine"):
            from backend.utils.domains.auto_generation.prompt_templates import TASK_TYPE_ALLOWED_ACTIONS

            actions = TASK_TYPE_ALLOWED_ACTIONS.get(task_type)
            if actions:
                allowed_actions = "\n".join(f"  - {a}" for a in actions)

        # Opt 5: Anti-pattern warnings from ErrorKnowledgeBase
        anti_pattern_warnings = ""
        if self.context._is_small_model() or self.context._opt_enabled("opt5_anti_pattern_injection"):
            try:
                language = self.context.infer_language(file_path)
                warnings_text = self.context.error_knowledge_base.get_prevention_warnings(
                    file_path, project_type=project_name, language=language
                )
                if warnings_text:
                    anti_pattern_warnings = warnings_text
                    self.context.logger.info(f"[Opt5] Anti-pattern warnings injected for '{file_path}'")
            except Exception:
                pass

        # Feature 2: Few-shot examples from fragment store
        few_shot_section = ""
        _few_shot_cfg = getattr(self.context, "config", {})
        if isinstance(_few_shot_cfg, dict):
            _few_shot_cfg = _few_shot_cfg.get("few_shot_store", {})
        else:
            _few_shot_cfg = {}
        if _few_shot_cfg.get("enabled", True):
            try:
                _fs_language = self.context.infer_language(file_path)
                _fs_purpose = task.get("description", task.get("title", ""))
                _examples = await self.context.fragment_cache.get_similar_examples(
                    language=_fs_language, purpose=_fs_purpose, max_examples=2
                )
                if _examples:
                    _lines = ["## FEW-SHOT EXAMPLES (similar past successful files):"]
                    for _ex_purpose, _ex_code in _examples:
                        _lines.append(f"### Purpose: {_ex_purpose}")
                        _lines.append(f"```\n{_ex_code[:800]}\n```")
                    few_shot_section = "\n".join(_lines)
            except Exception:
                pass

        return {
            "context_files_content": context_files_content,
            "logic_plan_section": logic_plan_section,
            "allowed_actions": allowed_actions,
            "anti_pattern_warnings": anti_pattern_warnings,
            "few_shot_section": few_shot_section,
        }

    async def _save_task_result(
        self,
        file_path: str,
        content: str,
        task: Dict[str, Any],
        task_id: str,
        title: str,
        project_root: Path,
        generated_files: Dict[str, str],
        backlog: List[Dict[str, Any]],
        completed_task_ids: List[str],
        completed_tasks: int,
        total_tasks: int,
    ) -> None:
        """Persist a successfully generated file and update progress tracking."""
        generated_files[file_path] = content
        self.context.file_manager.write_file(project_root / file_path, content)

        # Feature 2: Store as successful example for future few-shot use
        _store_cfg = getattr(self.context, "config", {})
        if isinstance(_store_cfg, dict):
            _store_cfg = _store_cfg.get("few_shot_store", {})
        else:
            _store_cfg = {}
        if _store_cfg.get("enabled", True):
            try:
                _s_language = self.context.infer_language(file_path)
                _s_purpose = task.get("description", title)
                await self.context.fragment_cache.store_example(language=_s_language, purpose=_s_purpose, code=content)
            except Exception:
                pass

        task["status"] = "done"

        # Update step progress for prompt injection in subsequent LLM calls
        completed_task_ids.append(task_id)
        next_task_index = backlog.index(task) + 1
        next_title = backlog[next_task_index].get("title", "") if next_task_index < total_tasks else "done"
        self.context.update_step_progress(
            current_index=completed_tasks,
            total=total_tasks,
            completed=completed_task_ids,
            current_objective=next_title,
        )

        await self.context.event_publisher.publish(
            "agent_board_update", action="move_task", task_id=task_id, new_status="done"
        )

    async def _generate_with_plan(
        self,
        file_path: str,
        plan: Dict,
        related: Dict[str, str],
        readme: str,
        structure: Dict,
    ) -> str:
        """Use enhanced generator with detailed plan."""
        try:
            from backend.utils.domains.auto_generation.enhanced_file_content_generator import (
                EnhancedFileContentGenerator,
            )

            enhanced_gen = EnhancedFileContentGenerator(
                self.context.llm_manager.get_client("coder"),
                self.context.logger,
                self.context.response_parser,
            )

            content = await enhanced_gen.generate_file_with_plan(file_path, plan, "", readme, structure, related)
            return content
        except Exception as e:
            self.context.logger.debug(f"Enhanced generation failed, falling back: {e}")
            return None

    def _validate_file_content(self, file_path: str, content: str, plan: Dict) -> bool:
        """
        Validate that generated content is complete, correct, and free of hallucinations.
        """
        stripped_content = content.strip()

        # 1. Minimum payload check (< 20 chars for main files is usually an error or hallucination)
        is_main_file = any(x in file_path.lower() for x in ["main", "app", "server", "index", "core"])
        if is_main_file and len(stripped_content) < 20:
            self.context.logger.warning(
                f"    Payload too small ({len(stripped_content)} chars) for main file: {file_path}"
            )
            return False

        if len(stripped_content) < 5:
            return False

        # 2. Hallucination detection (Phrases outside comments)
        hallucination_phrases = [
            "Here is the code",
            "Sure, I can help",
            "Certainly!",
            "I've implemented",
            "As a senior developer",
            "Hope this helps",
            "example_function",
            "proper Python syntax",
            "SELECT * FROM table_name",
        ]

        # Simple heuristic: if these phrases appear in the first 200 chars and are not in comments
        prefix = stripped_content[:200].lower()
        for phrase in hallucination_phrases:
            if phrase.lower() in prefix:
                # Check if it's likely a comment (simple check)
                if not any(prefix.startswith(c) for c in ["#", "//", "/*", '"""', "'''"]):
                    self.context.logger.warning(f'    Possible hallucination detected in {file_path}: "{phrase}"')
                    return False

        # 3. Plan compliance: Check for required exports
        # Skip for entry-point files (main.py, app.py, etc.) which don't export symbols
        if not is_main_file:
            exports = plan.get("exports", [])
            for export in exports:
                if export and export not in content:
                    self.context.logger.warning(f"    Missing expected export: {export}")
                    return False

        # 4. TODO density check
        if "TODO" in content and content.count("TODO") > 5:
            self.context.logger.warning(f"    High TODO density ({content.count('TODO')}) in {file_path}")
            return False

        return True

    def _format_logic_plan_for_prompt(self, plan: Dict[str, Any]) -> str:
        """Serialize the logic plan for a file into a compact, LLM-readable section (Fix 1)."""
        if not plan:
            return "(No architecture plan available for this file)"
        lines = []
        exports = plan.get("exports", [])
        if exports:
            lines.append("Exports (MUST implement all, with the exact construct type):")
            for e in exports:
                lines.append(f"  - {e}")
        imports_list = plan.get("imports", [])
        if imports_list:
            lines.append("Imports to use:")
            for i in imports_list:
                lines.append(f"  - {i}")
        main_logic = plan.get("main_logic", [])
        if main_logic:
            lines.append("Implementation steps:")
            for step in main_logic:
                lines.append(f"  {step}")
        return "\n".join(lines) if lines else "(Plan has no structured details)"

    async def _run_tdd_loop(self, file_path: str, content: str, max_retries: int = 2) -> str:
        """F2: TDD Agéntico — generate a minimal unit test, run it, auto-correct on failure.

        Only operates on Python files. For all other file types the content is
        returned unchanged immediately.

        Args:
            file_path: Relative path of the source file being generated.
            content: Generated source code to validate via testing.
            max_retries: Maximum correction attempts on test failure.

        Returns:
            Potentially corrected content, or the original if tests pass or
            if test generation/execution encounters an unrecoverable error.
        """
        import subprocess
        import tempfile

        if not file_path.endswith(".py"):
            return content

        try:
            test_code = await self._generate_minimal_test(file_path, content)
            if not test_code:
                return content

            with tempfile.TemporaryDirectory() as tmpdir:
                from pathlib import Path as _Path

                tmp_path = _Path(tmpdir)
                # Write source module
                src_file = tmp_path / "src_module.py"
                src_file.write_text(content, encoding="utf-8")
                # Write minimal test
                test_file = tmp_path / "test_minimal.py"
                test_file.write_text(test_code, encoding="utf-8")

                for attempt in range(1, max_retries + 1):
                    result = subprocess.run(
                        ["python", "-m", "pytest", str(test_file), "-x", "--tb=short", "-q"],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        cwd=str(tmp_path),
                    )
                    if result.returncode == 0:
                        self.context.logger.info(f"  [TDD] Tests passed for {file_path} (attempt {attempt})")
                        break

                    error_output = (result.stdout + result.stderr)[-1500:]
                    self.context.logger.info(f"  [TDD] Test failed (attempt {attempt}/{max_retries}), correcting...")
                    content = await self._correct_via_tdd_error(file_path, content, error_output)
                    src_file.write_text(content, encoding="utf-8")

        except subprocess.TimeoutExpired:
            self.context.logger.warning(f"  [TDD] Test execution timed out for {file_path} — skipping")
        except FileNotFoundError:
            self.context.logger.warning("  [TDD] pytest not available — skipping TDD loop")
        except Exception as exc:
            self.context.logger.warning(f"  [TDD] Unexpected error for {file_path}: {exc}")

        return content

    async def _generate_minimal_test(self, file_path: str, content: str) -> str:
        """Ask the LLM for a single unit test for the most complex function in *content*."""
        try:
            import ast as _ast

            tree = _ast.parse(content)
            func_names = [
                node.name
                for node in _ast.walk(tree)
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and not node.name.startswith("_")
            ]
            if not func_names:
                return ""
            # Pick the function with the most lines as heuristic for "most complex"
            target_func = func_names[0]
        except SyntaxError:
            return ""

        try:
            from backend.utils.core.llm.prompt_loader import PromptLoader

            loader = PromptLoader()
            prompts = await loader.load_prompt("domains/auto_generation/code_gen.yaml")
            system = prompts.get("tdd_minimal_test", {}).get("system", "")
            user_template = prompts.get("tdd_minimal_test", {}).get("user", "")
            if not system or not user_template:
                return ""
            user = user_template.format(
                file_path="src_module.py",
                file_content=content[:3000],
                function_to_test=target_func,
            )
            response_data, _ = self.context.llm_manager.get_client("coder").chat(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                tools=[],
                options_override={"temperature": 0.1},
            )
            raw = response_data.get("content", "")
            import re as _re

            match = _re.search(r"```(?:python)?\n(.*?)```", raw, _re.DOTALL)
            return match.group(1).strip() if match else raw.strip()
        except Exception as exc:
            self.context.logger.debug(f"  [TDD] Test generation failed: {exc}")
            return ""

    async def _correct_via_tdd_error(self, file_path: str, content: str, error_output: str) -> str:
        """Ask the LLM to fix *content* given the pytest *error_output*."""
        try:
            correction_prompt = (
                f"The following Python code failed its unit test.\n\n"
                f"FILE: {file_path}\n"
                f"CODE:\n```python\n{content[:3000]}\n```\n\n"
                f"TEST ERROR OUTPUT:\n{error_output}\n\n"
                f"Fix ONLY the code that caused the test to fail. "
                f"Return the corrected Python code inside ```python ... ``` tags."
            )
            response_data, _ = self.context.llm_manager.get_client("coder").chat(
                messages=[
                    {"role": "system", "content": "You are a Python debugging expert."},
                    {"role": "user", "content": correction_prompt},
                ],
                tools=[],
                options_override={"temperature": 0.1},
            )
            raw = response_data.get("content", "")
            import re as _re

            match = _re.search(r"```(?:python)?\n(.*?)```", raw, _re.DOTALL)
            corrected = match.group(1).strip() if match else ""
            return corrected if len(corrected) > 20 else content
        except Exception as exc:
            self.context.logger.debug(f"  [TDD] Correction LLM call failed: {exc}")
            return content

    def _check_output_contract(self, file_path: str, content: str, task_type: str) -> str:
        """Validate that *content* respects the structural contract for *task_type* (Opt 3).

        Checks structural constraints — NOT logic correctness:
        - ``define_imports``: must not contain function or class definitions
        - ``implement_function``: must contain at least one function or class definition
        - ``write_tests``: must contain at least one ``test_`` prefixed identifier

        Uses ``ast.parse`` for Python files; regex heuristics for others.

        Args:
            file_path: Path of the file being generated (used to select checker).
            content: Generated code to validate.
            task_type: Backlog task type string.

        Returns:
            Empty string if the contract is satisfied, or a short error description.
        """
        import ast as _ast
        import re as _re

        if not content:
            return ""

        is_python = file_path.endswith(".py")

        if task_type == "define_imports":
            if is_python:
                try:
                    tree = _ast.parse(content)
                    for node in _ast.walk(tree):
                        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)):
                            return (
                                "define_imports step must contain ONLY import statements — "
                                "no function or class definitions allowed."
                            )
                except SyntaxError:
                    pass  # Syntax validation handles this separately
            else:
                if _re.search(r"\b(function|class|def)\s+\w+", content):
                    return (
                        "define_imports step must contain ONLY import statements — "
                        "no function or class definitions allowed."
                    )

        elif task_type == "implement_function":
            if is_python:
                try:
                    tree = _ast.parse(content)
                    has_def = any(
                        isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef, _ast.ClassDef)) for n in _ast.walk(tree)
                    )
                    if not has_def:
                        return "implement_function step must contain at least one function or class definition."
                except SyntaxError:
                    pass
            else:
                if not _re.search(r"\b(function|class|def)\s+\w+", content):
                    return "implement_function step must contain at least one function or class definition."

        elif task_type == "write_tests":
            if not _re.search(r"\btest_\w+", content):
                return "write_tests step must contain at least one test function (name must start with 'test_')."

        return ""

    def _topological_sort(self, backlog: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort backlog tasks in dependency order using Kahn's algorithm (Fix 3).

        Tasks with no dependencies come first; if there are cycles or missing
        dependency references the original order is preserved with a warning.
        """
        id_to_task: Dict[str, Dict] = {t["id"]: t for t in backlog if "id" in t}
        if not id_to_task:
            return backlog

        # Build adjacency and in-degree
        in_degree: Dict[str, int] = {tid: 0 for tid in id_to_task}
        dependents: Dict[str, List[str]] = {tid: [] for tid in id_to_task}

        for task in backlog:
            tid = task.get("id")
            if not tid:
                continue
            for dep in task.get("dependencies", []):
                if dep in id_to_task:
                    in_degree[tid] = in_degree.get(tid, 0) + 1
                    dependents[dep].append(tid)

        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        sorted_ids: List[str] = []

        while queue:
            current = queue.pop(0)
            sorted_ids.append(current)
            for dependent in dependents.get(current, []):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(sorted_ids) != len(id_to_task):
            self.context.logger.warning("  ⚠ Cycle detected in backlog dependencies — keeping original order")
            return backlog

        # Preserve tasks without IDs (append at end)
        tasks_without_id = [t for t in backlog if "id" not in t]
        sorted_tasks = [id_to_task[tid] for tid in sorted_ids] + tasks_without_id
        self.context.logger.info(f"  Backlog sorted by dependencies: {sorted_ids}")
        return sorted_tasks

    def _is_binary_file(self, file_path: str) -> bool:
        """Check if the file is a binary format that shouldn't be generated by LLM."""
        binary_extensions = {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".ico",
            ".webp",
            ".wav",
            ".mp3",
            ".ogg",
            ".m4a",
            ".flac",
            ".zip",
            ".tar",
            ".gz",
            ".7z",
            ".rar",
            ".pdf",
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".eot",
            ".ttf",
            ".woff",
            ".woff2",
        }
        return Path(file_path).suffix.lower() in binary_extensions

    def _infer_language(self, file_path: str) -> str:
        """Infer programming language from file path. Copied from AutoAgent for now."""
        ext = Path(file_path).suffix.lower()
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
        }
        return language_map.get(ext, "unknown")
