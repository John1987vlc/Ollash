import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

from src.utils.core.ollama_client import OllamaClient
from src.utils.core.agent_logger import AgentLogger
from src.utils.core.token_tracker import TokenTracker
from src.utils.core.llm_response_parser import LLMResponseParser
from src.utils.core.file_validator import FileValidator
from src.utils.domains.auto_generation.project_planner import ProjectPlanner
from src.utils.domains.auto_generation.structure_generator import StructureGenerator
from src.utils.domains.auto_generation.file_content_generator import FileContentGenerator
from src.utils.domains.auto_generation.file_refiner import FileRefiner
from src.utils.domains.auto_generation.file_completeness_checker import FileCompletenessChecker
from src.utils.domains.auto_generation.project_reviewer import ProjectReviewer
from src.utils.domains.auto_generation.improvement_suggester import ImprovementSuggester
from src.utils.domains.auto_generation.improvement_planner import ImprovementPlanner
from src.utils.domains.auto_generation.senior_reviewer import SeniorReviewer # New Import


class AutoAgent:
    """Orchestrates the multi-phase project creation pipeline.

    Phases:
        1. README generation (planner LLM)
        2. JSON structure generation (prototyper LLM)
        3. Empty file scaffolding
        4. File content generation (prototyper LLM)
        5. File refinement (coder LLM)
        5.5. Verification loop - validate & fix (coder LLM)
        6. Final review (generalist LLM)
        7. Iterative Improvement (suggester, improvement_planner, coder)
        8. Senior Review (senior_reviewer)
    """

    LLM_ROLES = [
        ("prototyper", "prototyper_model", "llama2:13b", 600),
        ("coder", "coder_model", "qwen:7b-chat", 480),
        ("planner", "planner_model", "mistral:7b", 900),
        ("generalist", "generalist_model", "mistral:7b-instruct", 300),
        ("suggester", "suggester_model", "mistral:7b-instruct", 300), # Using generalist model for suggestions
        ("improvement_planner", "improvement_planner_model", "mistral:7b", 900), # Using planner model for planning
        ("senior_reviewer", "senior_reviewer_model", "mistral:7b-instruct", 600), # New Role
    ]

    def __init__(self, config_path: str = "config/settings.json"):
        with open(config_path, "r") as f:
            self.config = json.load(f)

        self.url = os.environ.get(
            "MOLTBOT_OLLAMA_URL",
            self.config.get("ollama_url", "http://localhost:11434"),
        )
        self.logger = AgentLogger(log_file=str(Path("logs") / "auto_agent.log"))
        self.token_tracker = TokenTracker()
        self.response_parser = LLMResponseParser()
        self.file_validator = FileValidator(logger=self.logger)

        self.llm_clients: Dict[str, OllamaClient] = {}
        self._initialize_llm_clients()

        # Phase services (dependency injection)
        self.planner = ProjectPlanner(self.llm_clients["planner"], self.logger)
        self.structure_gen = StructureGenerator(
            self.llm_clients["prototyper"], self.logger, self.response_parser
        )
        self.content_gen = FileContentGenerator(
            self.llm_clients["prototyper"], self.logger, self.response_parser
        )
        self.refiner = FileRefiner(
            self.llm_clients["coder"], self.logger, self.response_parser
        )
        self.completeness_checker = FileCompletenessChecker(
            self.llm_clients["coder"],
            self.logger,
            self.response_parser,
            self.file_validator,
            max_retries_per_file=2,
        )
        self.reviewer = ProjectReviewer(self.llm_clients["generalist"], self.logger)
        self.suggester = ImprovementSuggester(
            self.llm_clients["suggester"], self.logger, self.response_parser
        )
        self.improvement_planner = ImprovementPlanner(
            self.llm_clients["improvement_planner"], self.logger, self.response_parser
        )
        self.senior_reviewer = SeniorReviewer( # New Service
            self.llm_clients["senior_reviewer"], self.logger, self.response_parser
        )

        self.generated_projects_dir = Path("generated_projects/auto_agent_projects")
        self.generated_projects_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info("AutoAgent initialized.")

    def _initialize_llm_clients(self):
        """Create OllamaClient instances for each specialized LLM role."""
        llm_config = self.config.get("auto_agent_llms", {})
        timeout_config = self.config.get("auto_agent_timeouts", {})

        for role, model_key, default_model, default_timeout in self.LLM_ROLES:
            self.llm_clients[role] = OllamaClient(
                url=self.url,
                model=llm_config.get(model_key, default_model),
                timeout=timeout_config.get(role, default_timeout),
                logger=self.logger,
                config=self.config,
            )
        self.logger.info("AutoAgent LLM clients initialized.")

    def create_project(self, project_description: str, project_name: str = "new_project", num_refine_loops: int = 0) -> Path:
        """Orchestrate the full project creation pipeline.

        Returns the path to the generated project root.
        """
        project_root = self.generated_projects_dir / project_name
        project_root.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Starting project '{project_name}' at {project_root}")

        # Phase 1: README
        self.logger.info("PHASE 1: Generating README.md...")
        readme = self.planner.generate_readme(project_description)
        self._save_file(project_root / "README.md", readme)
        self.logger.info("PHASE 1 complete.")

        # Phase 2: JSON structure
        self.logger.info("PHASE 2: Generating project structure...")
        structure = self.structure_gen.generate(readme, max_retries=3)
        if not structure or (not structure.get("files") and not structure.get("folders")):
            self.logger.error("Could not generate valid structure. Using fallback.")
            structure = StructureGenerator.create_fallback_structure(readme)
        self._save_file(project_root / "project_structure.json", json.dumps(structure, indent=2))
        file_paths = StructureGenerator.extract_file_paths(structure)
        self.logger.info(f"PHASE 2 complete: {len(file_paths)} files planned.")

        # Phase 3: Empty files
        self.logger.info("PHASE 3: Creating empty placeholders...")
        StructureGenerator.create_empty_files(project_root, structure)
        self.logger.info("PHASE 3 complete.")

        # Phase 4: Content generation
        self.logger.info("PHASE 4: Generating file contents...")
        files: Dict[str, str] = {}
        for idx, rel_path in enumerate(file_paths, 1):
            self.logger.info(f"  [{idx}/{len(file_paths)}] {rel_path}")
            try:
                content = self.content_gen.generate_file(
                    rel_path, readme, structure, dict(list(files.items())[-5:])
                )
                files[rel_path] = content or ""
                if content:
                    self._save_file(project_root / rel_path, content)
            except Exception as e:
                self.logger.error(f"  Error generating {rel_path}: {e}")
                files[rel_path] = ""
        self.logger.info("PHASE 4 complete.")

        # Phase 5: Refinement
        self.logger.info("PHASE 5: Refining files...")
        for idx, (rel_path, content) in enumerate(list(files.items()), 1):
            if not content or len(content) < 10:
                continue
            self.logger.info(f"  [{idx}/{len(file_paths)}] Refining {rel_path}")
            try:
                refined = self.refiner.refine_file(rel_path, content, readme[:1000])
                if refined:
                    files[rel_path] = refined
                    self._save_file(project_root / rel_path, refined)
            except Exception as e:
                self.logger.error(f"  Error refining {rel_path}: {e}")
        self.logger.info("PHASE 5 complete.")

        # Phase 5.5: Verification loop
        self.logger.info("PHASE 5.5: Verification loop...")
        files = self.completeness_checker.verify_and_fix(files, readme[:1000])
        for rel_path, content in files.items():
            if content:
                self._save_file(project_root / rel_path, content)
        self.logger.info("PHASE 5.5 complete.")

        # Phase 6: Final review
        self.logger.info("PHASE 6: Final review...")
        validation_summary = self.completeness_checker.get_validation_summary(files)
        try:
            review = self.reviewer.review(project_name, readme[:500], file_paths, validation_summary)
            self._save_file(project_root / "PROJECT_REVIEW.md", review)
        except Exception as e:
            self.logger.error(f"Error during review: {e}")

        # New Iterative Improvement Phase (Phase 7)
        if num_refine_loops > 0:
            self.logger.info(f"PHASE 7: Starting Iterative Improvement Loops ({num_refine_loops} loops)...")
            for loop_num in range(num_refine_loops):
                self.logger.info(f"PHASE 7: Iteration {loop_num + 1}/{num_refine_loops}")

                # 1. Suggest improvements
                suggestions = self.suggester.suggest_improvements(
                    project_description, readme, structure, files, loop_num
                )
                self.logger.info(f"  Suggested Improvements ({len(suggestions)}): {', '.join(suggestions[:3])}...")
                if not suggestions:
                    self.logger.info("  No further improvements suggested. Ending refinement loops.")
                    break

                # 2. Plan improvements
                plan = self.improvement_planner.generate_plan(
                    suggestions, project_description, readme, structure, files
                )
                if not plan or not plan.get("actions"):
                    self.logger.warning("  Improvement plan could not be generated or was empty. Skipping this iteration.")
                    continue
                self.logger.info(f"  Improvement Plan generated with {len(plan.get('actions', []))} actions.")

                # 3. Implement improvements
                self.logger.info("  Implementing plan...")
                files, structure, file_paths = self._implement_plan(
                    plan, project_root, readme, structure, files, file_paths
                )

                # Re-run refinement and verification after each loop to ensure quality
                self.logger.info(f"  Re-running Phase 5: Refinement after improvement loop {loop_num + 1}...")
                for idx, (rel_path, content) in enumerate(list(files.items()), 1):
                    if not content or len(content) < 10:
                        continue
                    self.logger.info(f"    Refining {rel_path}")
                    try:
                        refined = self.refiner.refine_file(rel_path, content, readme[:1000])
                        if refined:
                            files[rel_path] = refined
                            self._save_file(project_root / rel_path, refined)
                    except Exception as e:
                        self.logger.error(f"    Error refining {rel_path}: {e}")

                self.logger.info(f"  Re-running Phase 5.5: Verification after improvement loop {loop_num + 1}...")
                files = self.completeness_checker.verify_and_fix(files, readme[:1000])
                for rel_path, content in files.items():
                    if content:
                        self._save_file(project_root / rel_path, content)

            self.logger.info("PHASE 7: Iterative Improvement complete.")
        
        # New Iterative Senior Review Phase (Phase 8)
        self.logger.info("PHASE 8: Starting Senior Review...")
        review_passed = False
        review_attempt = 0
        max_review_attempts = 3 # Define max attempts for senior review
        while not review_passed and review_attempt < max_review_attempts:
            review_attempt += 1
            self.logger.info(f"PHASE 8: Senior Review Attempt {review_attempt}/{max_review_attempts}...")
            
            review_results = self.senior_reviewer.perform_review(
                project_description, project_name, readme, structure, files, review_attempt
            )

            if review_results.get("status") == "passed":
                review_passed = True
                self.logger.info("PHASE 8: Senior Review Passed!")
                self._save_file(project_root / "SENIOR_REVIEW_SUMMARY.md", review_results.get("summary", "Senior review passed."))
            else:
                self.logger.warning(f"PHASE 8: Senior Review Failed. Issues found: {len(review_results.get('issues', []))}")
                self._save_file(project_root / f"SENIOR_REVIEW_ISSUES_ATTEMPT_{review_attempt}.md", review_results.get("summary", "Senior review failed with unspecified issues."))
                
                # Try to fix the issues identified by the senior reviewer
                if review_results.get("issues"):
                    self.logger.info("  Attempting to fix senior review issues...")
                    # This is a simplified implementation. A more robust solution would map issues
                    # to specific file modifications. For now, we'll use a generic refinement/verification cycle.
                    
                    # Placeholder for more targeted fixes based on review_results.get("issues")
                    # For a real implementation, 'issues' would drive targeted modifications
                    
                    self.logger.info("  Re-running Phase 5: Refinement based on senior review issues...")
                    for idx, (rel_path, content) in enumerate(list(files.items()), 1):
                        # Only refine files mentioned in issues, or all files for a broad fix attempt
                        if not content or len(content) < 10:
                            continue
                        self.logger.info(f"    Refining {rel_path}")
                        try:
                            # Consider sending review_results.get("issues") to refiner for targeted fix
                            # Pass relevant issues to the refiner
                            issues_for_file = [issue for issue in review_results["issues"] if issue.get("file") == rel_path]
                            refined = self.refiner.refine_file(rel_path, content, readme[:1000], issues_for_file)
                            if refined:
                                files[rel_path] = refined
                                self._save_file(project_root / rel_path, refined)
                        except Exception as e:
                            self.logger.error(f"    Error refining {rel_path} during senior review fix: {e}")

                    self.logger.info("  Re-running Phase 5.5: Verification based on senior review issues...")
                    # The completeness_checker could also be made aware of specific issues for targeted fixes
                    files = self.completeness_checker.verify_and_fix(files, readme[:1000]) # Could pass specific issues here
                    for rel_path, content in files.items():
                        if content:
                            self._save_file(project_root / rel_path, content)
                else:
                    self.logger.warning("  No specific issues provided by senior reviewer to fix.")

        if not review_passed:
            self.logger.error("PHASE 8: Senior Review failed after multiple attempts. Manual intervention may be required.")
            self._save_file(project_root / "SENIOR_REVIEW_FAILED.md", "Senior review failed after multiple attempts.")
        
        self.logger.info(f"Project '{project_name}' completed at {project_root}")
        self.logger.info(f"  Generated {len(file_paths)} files")
        return project_root

    def _implement_plan(
        self,
        plan: Dict,
        project_root: Path,
        readme_content: str,
        json_structure: Dict,
        current_files: Dict[str, str],
        current_file_paths: List[str]
    ) -> Tuple[Dict[str, str], Dict, List[str]]:
        """Implements the given plan, updating files and structure."""
        actions = plan.get("actions", [])
        updated_files = current_files.copy()
        updated_structure = json_structure.copy()
        updated_file_paths = current_file_paths.copy()

        for action in actions:
            action_type = action.get("type")
            path = action.get("path")
            content = action.get("content") # For 'create' or 'modify'
            target_folder = action.get("target_folder") # For 'create_folder'

            if not path and action_type != "create_folder":
                self.logger.warning(f"  Skipping action due to missing path: {action}")
                continue

            abs_path = project_root / Path(path) if path else None

            try:
                if action_type == "create_file":
                    self.logger.info(f"    Creating new file: {path}")
                    # Use content_gen to generate new file content, or use provided content
                    generated_content = content
                    if not generated_content:
                        generated_content = self.content_gen.generate_file(
                            path, readme_content, updated_structure, updated_files
                        )
                    if generated_content:
                        self._save_file(abs_path, generated_content)
                        updated_files[path] = generated_content
                        # Update structure and file_paths (simplified, might need more robust update)
                        if path not in updated_file_paths:
                            updated_file_paths.append(path)
                        # More complex logic needed to insert into json_structure dict based on path

                elif action_type == "modify_file":
                    self.logger.info(f"    Modifying file: {path}")
                    if abs_path and abs_path.exists():
                        current_file_content = abs_path.read_text(encoding="utf-8")
                        # Use refiner to apply changes, or apply provided content directly
                        modified_content = content
                        if not modified_content:
                            modified_content = self.refiner.refine_file(
                                path, current_file_content, readme_content[:1000]
                            )
                        if modified_content:
                            self._save_file(abs_path, modified_content)
                            updated_files[path] = modified_content
                    else:
                        self.logger.warning(f"    File not found for modification: {path}")

                elif action_type == "create_folder":
                    self.logger.info(f"    Creating new folder: {target_folder}")
                    folder_path = project_root / Path(target_folder)
                    folder_path.mkdir(parents=True, exist_ok=True)
                    # More complex logic needed to insert into json_structure dict based on path

                elif action_type == "delete_file":
                    self.logger.info(f"    Deleting file: {path}")
                    if abs_path and abs_path.exists():
                        abs_path.unlink()
                        if path in updated_files:
                            del updated_files[path]
                        if path in updated_file_paths:
                            updated_file_paths.remove(path)
                    # More complex logic needed to remove from json_structure dict

                else:
                    self.logger.warning(f"    Unknown action type: {action_type}")

            except Exception as e:
                self.logger.error(f"  Error during plan implementation for {path}: {e}")

        # After all actions, re-extract file paths from the (potentially updated) structure
        # This is a robust way to ensure file_paths is consistent
        # For now, a simplified update to json_structure is used, more robust update is needed.
        # updated_file_paths = StructureGenerator.extract_file_paths(updated_structure)

        return updated_files, updated_structure, updated_file_paths
    
    @staticmethod
    def _save_file(file_path: Path, content: str):
        """Save content to a file, creating parent directories as needed."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content.strip())