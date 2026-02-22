from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase
from backend.utils.core.llm.parallel_generator import GenerationTask
from backend.utils.domains.auto_generation.prompt_templates import AutoGenPrompts
from backend.utils.core.analysis.context_distiller import ContextDistiller


class FileContentGenerationPhase(IAgentPhase):
    """
    Phase 4: Generates the content for all planned files, potentially in parallel.
    NOW USES LOGIC PLANS for more accurate, complete implementations.
    Handles dependency awareness, incremental validation, and error logging.
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

        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 4: Executing Agile Backlog with Self-Reflection...")
        self.context.event_publisher.publish(
            "phase_start", phase="4", message="Starting iterative micro-task execution with XML/AST validation"
        )

        backlog = getattr(self.context, "backlog", [])
        if not backlog and hasattr(self.context, "logic_plan"):
             for i, (path, plan) in enumerate(self.context.logic_plan.items()):
                 backlog.append({
                     "id": f"TASK-{i:03d}",
                     "title": f"Implement {path}",
                     "description": plan.get("purpose", f"Generate {path}"),
                     "file_path": path,
                     "task_type": "create_file",
                     "dependencies": [],
                     "context_files": []
                 })

        total_tasks = len(backlog)
        completed_tasks = 0

        for task in backlog:
            task_id = task.get("id", "UNKNOWN")
            title = task.get("title", "Untitled")
            file_path = task.get("file_path", "")
            task_type = task.get("task_type", "create_file")

            self.context.logger.info(f"  [Task {completed_tasks+1}/{total_tasks}] {task_id}: {title}")
            
            # CRITICAL: Binary Guard - Skip LLM call for binary files
            if self._is_binary_file(file_path):
                self.context.logger.info(f"    Skipped: Binary file detected ({file_path})")
                generated_files[file_path] = ""
                # Move to done in Kanban anyway
                self.context.event_publisher.publish("agent_board_update", action="move_task", task_id=task_id, new_status="done")
                completed_tasks += 1
                continue

            # Notify progress to Kanban Board
            self.context.event_publisher.publish("agent_board_update", action="move_task", task_id=task_id, new_status="in_progress")

            try:
                # 1. Distilled Context Preparation
                raw_context_files = self.context.select_related_files(file_path, generated_files)
                context_files_content = ContextDistiller.distill_batch(raw_context_files)

                # 2. Construct Sniper Prompt with XML requirements
                base_system, base_user = AutoGenPrompts.micro_task_execution(
                    title=title,
                    description=task.get("description", ""),
                    file_path=file_path,
                    task_type=task_type,
                    readme_content=readme_content[:1000],
                    context_files_content=context_files_content[:4000]
                )
                
                system_prompt = base_system + "\n\nCRITICAL RULE: Analyze the problem step-by-step inside <thinking_process>. Then, provide ONLY the final code inside <code_created>. Do not use markdown code blocks outside these tags."
                user_prompt = base_user

                content = ""
                attempts = 0
                max_attempts = 3
                last_error = ""

                # 3. Self-Reflection and Correction Loop
                while attempts < max_attempts:
                    attempts += 1
                    current_user_prompt = user_prompt
                    if last_error:
                        current_user_prompt += f"\n\nRETRY DUE TO PREVIOUS ERROR:\n{last_error}\nPlease fix the error and respond strictly following the <thinking_process> and <code_created> format."

                    # 3. LLM Call
                    response_data, _ = self.context.llm_manager.get_client("coder").chat(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": current_user_prompt},
                        ],
                        tools=[],
                        options_override={"temperature": 0.1},
                    )

                    raw_response = response_data.get("content", "").strip()
                    
                    # 4. XML Extraction via Regex
                    import re
                    codigo_match = re.search(r"<code_created>([\s\S]*?)</code_created>", raw_response)

                    if not codigo_match:
                        last_error = "FORMAT FAILURE: You have not included the <code_created> tag in your response."
                        self.context.logger.warning(f"    ⚠ Attempt {attempts}: Missing XML tags.")
                        continue

                    content = codigo_match.group(1).strip()
                    # Clean residual markdown if the SLM included it inside tags
                    content = re.sub(r"```(?:\w+)?\n?", "", content).replace("```", "").strip()

                    # 5. AST/Syntax Validation
                    validation_result = self.context.files_ctx.validator.validate(file_path, content)
                    
                    if validation_result.status.name == "VALID":
                        self.context.logger.info(f"    ✓ {file_path} syntactically validated (Attempt {attempts})")
                        break
                    else:
                        last_error = f"SYNTAX ERROR: {validation_result.message}"
                        self.context.logger.warning(f"    ⚠ Attempt {attempts} failed validation: {validation_result.message}")
                        if attempts < max_attempts:
                            content = "" # Reset to force retry

                # 6. Final Save and Notification
                if content:
                    generated_files[file_path] = content
                    self.context.file_manager.write_file(project_root / file_path, content)
                    completed_tasks += 1
                    self.context.event_publisher.publish("agent_board_update", action="move_task", task_id=task_id, new_status="done")
                else:
                    self.context.logger.error(f"    ✖ Task {task_id} failed after {max_attempts} attempts.")

            except Exception as e:
                self.context.logger.error(f"Fatal error in task {task_id}: {e}")
                # Record error in knowledge base
                self.context.error_knowledge_base.record_error(
                    file_path, "micro_task_failure", str(e), task_id, title
                )

        self.context.event_publisher.publish(
            "phase_complete",
            phase="4",
            message=f"Agile execution finished: {completed_tasks}/{total_tasks} tasks completed",
        )
        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 4 complete.")

        return generated_files, initial_structure, file_paths

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

            content = enhanced_gen.generate_file_with_plan(file_path, plan, "", readme, structure, related)
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
            self.context.logger.warning(f"    Payload too small ({len(stripped_content)} chars) for main file: {file_path}")
            return False

        if len(stripped_content) < 5:
            return False

        # 2. Hallucination detection (Phrases outside comments)
        hallucination_phrases = [
            "Here is the code", "Sure, I can help", "Certainly!", 
            "I've implemented", "As a senior developer", "Hope this helps"
        ]
        
        # Simple heuristic: if these phrases appear in the first 200 chars and are not in comments
        prefix = stripped_content[:200].lower()
        for phrase in hallucination_phrases:
            if phrase.lower() in prefix:
                # Check if it's likely a comment (simple check)
                if not any(prefix.startswith(c) for c in ["#", "//", "/*", '"""', "'''"]):
                    self.context.logger.warning(f"    Possible hallucination detected in {file_path}: \"{phrase}\"")
                    return False

        # 3. Plan compliance: Check for required exports
        exports = plan.get("exports", [])
        for export in exports:
            if export and export not in content:
                self.context.logger.warning(f"    Missing expected export: {export}")
                # We don't fail immediately, but we could if we want extreme strictness
                # return False 

        # 4. TODO density check
        if "TODO" in content and content.count("TODO") > 5:
             self.context.logger.warning(f"    High TODO density ({content.count('TODO')}) in {file_path}")
             return False

        return True

    def _is_binary_file(self, file_path: str) -> bool:
        """Check if the file is a binary format that shouldn't be generated by LLM."""
        binary_extensions = {
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp',
            '.wav', '.mp3', '.ogg', '.m4a', '.flac',
            '.zip', '.tar', '.gz', '.7z', '.rar',
            '.pdf', '.exe', '.dll', '.so', '.dylib',
            '.eot', '.ttf', '.woff', '.woff2'
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
