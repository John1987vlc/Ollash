import json
import os
import re
import asyncio
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

from src.utils.core.ollama_client import OllamaClient
from src.utils.core.agent_logger import AgentLogger
from src.utils.core.llm_response_parser import LLMResponseParser
from src.utils.core.code_quarantine import CodeQuarantine

# NEW IMPORTS FOR IMPROVED FEATURES
from src.utils.core.fragment_cache import FragmentCache
from src.utils.core.dependency_graph import DependencyGraph
from src.utils.core.parallel_generator import (
    ParallelFileGenerator, GenerationTask, AsyncFileGenerationAdapter
)
from src.utils.core.error_knowledge_base import ErrorKnowledgeBase

# Import CoreAgent
from src.agents.core_agent import CoreAgent

from src.utils.domains.auto_generation.project_planner import ProjectPlanner
from src.utils.domains.auto_generation.structure_generator import StructureGenerator
from src.utils.domains.auto_generation.file_content_generator import FileContentGenerator
from src.utils.domains.auto_generation.file_refiner import FileRefiner
from src.utils.domains.auto_generation.file_completeness_checker import FileCompletenessChecker
from src.utils.domains.auto_generation.project_reviewer import ProjectReviewer
from src.utils.domains.auto_generation.improvement_suggester import ImprovementSuggester
from src.utils.domains.auto_generation.improvement_planner import ImprovementPlanner
from src.utils.domains.auto_generation.senior_reviewer import SeniorReviewer
from src.utils.domains.auto_generation.test_generator import TestGenerator
from src.utils.domains.auto_generation.contingency_planner import ContingencyPlanner
from src.utils.domains.auto_generation.structure_pre_reviewer import StructurePreReviewer
from src.utils.domains.auto_generation.multi_language_test_generator import (
    MultiLanguageTestGenerator, LanguageFrameworkMap
)


class AutoAgent(CoreAgent): # Inherit from CoreAgent
    """Orchestrates the multi-phase project creation pipeline.

    Phases:
        1. README generation (planner LLM)
        2. JSON structure generation (prototyper LLM)
        3. Empty file scaffolding
        4. File content generation (prototyper LLM)
        5. File refinement (coder LLM)
        5.5. Verification loop - validate & fix (coder LLM)
        5.6. Dependency reconciliation
        5.7. Test Generation and Execution (test_generator LLM)
        6. Final review (generalist LLM)
        7. Iterative Improvement (suggester, improvement_planner, coder)
        8. Senior Review (senior_reviewer)
    """

    def __init__(self, config_path: str = "config/settings.json", ollash_root_dir: Optional[Path] = None):
        super().__init__(config_path, ollash_root_dir, logger_name="AutoAgent") # Call parent constructor
        self.logger.info("AutoAgent specific initialization.")

        # Phase services (dependency injection)
        self.planner = ProjectPlanner(self.llm_clients["planner"], self.logger)
        self.structure_gen = StructureGenerator(
            self.llm_clients["prototyper"], self.logger, self.response_parser
        )
        
        # NEW: Fragment cache for performance
        cache_dir = self.ollash_root_dir / ".cache" / "fragments"
        self.fragment_cache = FragmentCache(cache_dir, self.logger, enable_persistence=True)
        self.fragment_cache.preload_common_fragments("python")
        self.fragment_cache.preload_common_fragments("javascript")
        
        self.content_gen = FileContentGenerator(
            self.llm_clients["prototyper"], self.logger, self.response_parser, 
            self.documentation_manager, self.fragment_cache
        )
        self.refiner = FileRefiner(
            self.llm_clients["coder"], self.logger, self.response_parser, self.documentation_manager, self.event_publisher
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
        
        # NEW: Multi-language test generator
        self.test_generator = MultiLanguageTestGenerator(
            self.llm_clients["test_generator"], self.logger, self.response_parser, self.command_executor
        )
        
        self.senior_reviewer = SeniorReviewer(
            self.llm_clients["senior_reviewer"], self.logger, self.response_parser
        )
        
        # NEW: Structure pre-reviewer
        self.structure_pre_reviewer = StructurePreReviewer(
            self.llm_clients["senior_reviewer"], self.logger, self.response_parser
        )
        
        self.contingency_planner = ContingencyPlanner(
            self.llm_clients["planner"], self.logger, self.response_parser
        )
        self.quarantine = CodeQuarantine(self.ollash_root_dir, self.logger)
        
        # NEW: Dependency graph and parallel generator
        self.dependency_graph = DependencyGraph(self.logger)
        self.parallel_generator = ParallelFileGenerator(
            self.logger, max_concurrent=3, max_requests_per_minute=10
        )
        
        # NEW: Error knowledge base for learning
        kb_dir = self.ollash_root_dir / ".cache" / "knowledge"
        self.error_kb = ErrorKnowledgeBase(kb_dir, self.logger, enable_persistence=True)

        self.generated_projects_dir = self.ollash_root_dir / "generated_projects" / "auto_agent_projects"
        self.generated_projects_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info("AutoAgent initialized with enhanced features.")

    def run(self, project_description: str, project_name: str = "new_project", num_refine_loops: int = 0,
            template_name: str = "default", python_version: str = "3.12", license_type: str = "MIT",
            include_docker: bool = False) -> Path:
        """Orchestrate the full project creation pipeline from scratch.

        This method first generates the project structure and then continues with
        the rest of the generation pipeline.
        Returns the path to the generated project root.
        """
        self.logger.info(f"[PROJECT_NAME:{project_name}] Starting full generation for '{project_name}'.")

        # Phase 1 & 2: Generate README and Structure
        readme, structure = self.generate_structure_only(
            project_description, project_name, template_name, python_version, license_type, include_docker
        )

        # Continue with the rest of the pipeline from Phase 2.5 onwards
        return self.continue_generation(
            project_description, project_name, readme, structure, num_refine_loops,
            template_name, python_version, license_type, include_docker
        )

    def generate_structure_only(self, project_description: str, project_name: str, template_name: str = "default",
                                python_version: str = "3.12", license_type: str = "MIT",
                                include_docker: bool = False) -> Tuple[str, Dict]:
        """Executes only Phase 1 (README) and Phase 2 (Structure Generation) of the pipeline."""
        project_root = self.generated_projects_dir / project_name
        project_root.mkdir(parents=True, exist_ok=True) # Ensure project dir exists for saving README

        self.logger.info(f"[PROJECT_NAME:{project_name}] Starting structure-only generation for '{project_name}' at {project_root}")
        
        # Phase 1: README
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 1: Generating README.md...")
        self.event_publisher.publish("phase_start", phase="1", message="Generating README.md")
        readme = self.planner.generate_readme(project_description, template_name, python_version, license_type, include_docker)
        self._save_file(project_root / "README.md", readme)
        self.event_publisher.publish("phase_complete", phase="1", message="README generated")
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 1 complete.")

        # Phase 2: JSON structure
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 2: Generating project structure using template '{template_name}'...")
        self.event_publisher.publish("phase_start", phase="2", message="Generating project structure")
        structure = self.structure_gen.generate(readme, max_retries=3, template_name=template_name,
                                                python_version=python_version, license_type=license_type, include_docker=include_docker)
        if not structure or (not structure.get("files") and not structure.get("folders")):
            self.logger.error(f"[PROJECT_NAME:{project_name}] Could not generate valid structure. Using fallback with template '{template_name}'.")
            structure = StructureGenerator.create_fallback_structure(readme, template_name=template_name,
                                                                      python_version=python_version, license_type=license_type, include_docker=include_docker)
        self._save_file(project_root / "project_structure.json", json.dumps(structure, indent=2))
        file_paths = StructureGenerator.extract_file_paths(structure)
        self.event_publisher.publish("phase_complete", phase="2", message="Project structure generated", data={"files_planned": len(file_paths)})
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 2 complete: {len(file_paths)} files planned.")
        
        return readme, structure
    
    def continue_generation(self, project_description: str, project_name: str, readme: str, structure: Dict,
                            template_name: str = "default", python_version: str = "3.12", license_type: str = "MIT",
                            include_docker: bool = False, num_refine_loops: int = 0) -> Path:
        """Continues the project generation pipeline from Phase 2.5 onwards, using a pre-generated README and structure."""
        self.logger.info(f"[PROJECT_NAME:{project_name}] Continuing generation for '{project_name}' from pre-generated structure.")
        return self._full_generation_pipeline(
            project_description, project_name, readme, structure, num_refine_loops,
            template_name, python_version, license_type, include_docker
        )

    def _full_generation_pipeline(self, project_description: str, project_name: str, readme: str, structure: Dict,
                                  num_refine_loops: int, template_name: str, python_version: str,
                                  license_type: str, include_docker: bool) -> Path:
        """Encapsulates the full generation pipeline from Phase 2.5 onwards."""
        project_root = self.generated_projects_dir / project_name
        file_paths = StructureGenerator.extract_file_paths(structure)
        
        # NEW Phase 2.5: Structure Pre-Review (Quality assurance before code generation)
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 2.5: PreReview of structure...")
        self.event_publisher.publish("phase_start", phase="2.5", message="Starting structure pre-review")
        structure_review = self.structure_pre_reviewer.review_structure(readme, structure, project_name)
        self._save_file(project_root / "STRUCTURE_REVIEW.json", json.dumps(structure_review.to_dict(), indent=2))
        
        if structure_review.status == "critical":
            self.logger.warning(f"[PROJECT_NAME:{project_name}] Structure has critical issues. Attempting fix...")
            # In critical cases, we could prompt for regeneration, but for now we continue
        else:
            self.logger.info(f"[PROJECT_NAME:{project_name}] Structure review: {structure_review.status} (score: {structure_review.quality_score:.1f})")
        
        self.event_publisher.publish("phase_complete", phase="2.5", message="Structure pre-review complete", 
                                   data={"quality_score": structure_review.quality_score})
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 2.5 complete.")

        # Phase 3: Empty files
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 3: Creating empty placeholders...")
        StructureGenerator.create_empty_files(project_root, structure)
        self.event_publisher.publish("phase_complete", phase="3", message="Empty files created")
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 3 complete.")

        # IMPROVED Phase 4: Parallel Content Generation with Dependency Awareness
        self.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 4: Generating file contents (parallelized)...")
        self.event_publisher.publish("phase_start", phase="4", message="Starting parallel content generation")
        
        # Build dependency graph for intelligent ordering
        self.dependency_graph.build_from_structure(structure, readme)
        generation_order = self.dependency_graph.get_generation_order()
        
        # Create generation tasks
        generation_tasks = []
        for file_path in generation_order:
            # Get context files for this file
            context_files = self.dependency_graph.get_context_for_file(file_path, max_depth=2)
            context = {
                "readme": readme,
                "structure": structure,
                "dependencies": context_files,
                "readme_excerpt": readme[:1000]
            }
            
            # Check error knowledge base for prevention tips
            language = self._infer_language(file_path)
            prevention_warnings = self.error_kb.get_prevention_warnings(
                file_path, project_name, language
            )
            context["error_warnings"] = prevention_warnings
            
            task = GenerationTask(
                file_path=file_path,
                context=context,
                priority=10 if any(x in file_path for x in ["__init__", "config", "utils"]) else 5,
            )
            generation_tasks.append(task)
        
        # Execute parallel generation
        files: Dict[str, str] = {}
        
        async def async_generate_wrapper():
            """Wrapper to call sync generation function asynchronously."""
            async def gen_file_async(file_path: str, context: Dict) -> Tuple[str, bool, str]:
                try:
                    related = self._select_related_files(file_path, files)
                    content = self.content_gen.generate_file(
                        file_path, context["readme"], context["structure"], related
                    )
                    files[file_path] = content or ""
                    if content:
                        self._save_file(project_root / file_path, content)
                    return (content or "", bool(content), None)
                except Exception as e:
                    self.logger.error(f"Error generating {file_path}: {e}")
                    files[file_path] = ""
                    # Record error in knowledge base
                    self.error_kb.record_error(
                        file_path, "generation_failure", str(e), "", context.get("readme_excerpt", "")
                    )
                    return ("", False, str(e))
            
            results = await self.parallel_generator.generate_files(
                generation_tasks,
                gen_file_async,
                progress_callback=lambda fp, completed, total: self.event_publisher.publish(
                    "tool_output", tool_name="content_generation", file=fp, 
                    progress=f"{completed}/{total}", status="success"
                ),
                dependency_order=generation_order,
            )
            return results
        
        # Run async generation
        try:
            generation_results = asyncio.run(async_generate_wrapper())
            stats = self.parallel_generator.get_statistics()
            self.logger.info(
                f"Phase 4 parallel generation: {stats['success']}/{stats['total']} files, "
                f"avg time: {stats['avg_time_per_file']:.2f}s"
            )
        except Exception as e:
            self.logger.error(f"Error in parallel generation: {e}. Falling back to sequential...")
            # Fallback to sequential generation
            for idx, rel_path in enumerate(file_paths, 1):
                self.event_publisher.publish("tool_start", tool_name="content_generation", file=rel_path, progress=f"{idx}/{len(file_paths)}")
                try:
                    related = self._select_related_files(rel_path, files)
                    content = self.content_gen.generate_file(rel_path, readme, structure, related)
                    files[rel_path] = content or ""
                    if content:
                        self._save_file(project_root / rel_path, content)
                except Exception as e2:
                    self.logger.error(f"Error generating {rel_path}: {e2}")
                    files[rel_path] = ""
        
        self.event_publisher.publish("phase_complete", phase="4", message="File contents generated")
        self.logger.info("PHASE 4 complete.")

        # Phase 5: Refinement
        self.logger.info("PHASE 5: Refining files...")
        for idx, (rel_path, content) in enumerate(list(files.items()), 1):
            if not content or len(content) < 10:
                continue
            self.event_publisher.publish("tool_start", tool_name="file_refinement", file=rel_path, progress=f"{idx}/{len(file_paths)}")
            self.logger.info(f"  [{idx}/{len(file_paths)}] Refining {rel_path}")
            try:
                refined = self.refiner.refine_file(rel_path, content, readme[:1000])
                if refined:
                    files[rel_path] = refined
                    self._save_file(project_root / rel_path, refined)
                    self.event_publisher.publish("tool_output", tool_name="file_refinement", file=rel_path, status="success")
                else:
                    self.event_publisher.publish("tool_output", tool_name="file_refinement", file=rel_path, status="skipped", message="Refinement not significant")
            except Exception as e:
                self.logger.error(f"  Error refining {rel_path}: {e}")
                self.event_publisher.publish("tool_output", tool_name="file_refinement", file=rel_path, status="error", message=str(e))
            self.event_publisher.publish("tool_end", tool_name="file_refinement", file=rel_path)
        self.event_publisher.publish("phase_complete", phase="5", message="Files refined")
        self.logger.info("PHASE 5 complete.")

        # Phase 5.5: Verification loop
        self.logger.info("PHASE 5.5: Verification loop...")
        self.event_publisher.publish("phase_start", phase="5.5", message="Starting verification loop")
        files = self.completeness_checker.verify_and_fix(files, readme[:1000])
        for rel_path, content in files.items():
            if content:
                self._save_file(project_root / rel_path, content)
        self.event_publisher.publish("phase_complete", phase="5.5", message="Verification loop complete")
        self.logger.info("PHASE 5.5 complete.")

        # Phase 5.55: Code Quarantine
        self.logger.info("PHASE 5.55: Code Quarantine...")
        self.event_publisher.publish("phase_start", phase="5.55", message="Starting code quarantine")
        for rel_path, content in files.items():
            if "subprocess" in content or "eval" in content:
                self.logger.warning(f"  Quarantining {rel_path} due to potentially unsafe content.")
                self.quarantine.quarantine_file(project_root / rel_path)
        self.event_publisher.publish("phase_complete", phase="5.55", message="Code quarantine complete")
        self.logger.info("PHASE 5.55 complete.")

        # Phase 5.56: License Compliance Check
        self.logger.info("PHASE 5.56: License Compliance Check...")
        self.event_publisher.publish("phase_start", phase="5.56", message="Starting license compliance check")
        for rel_path, content in files.items():
            if not self.policy_manager.is_license_compliant(project_root / rel_path):
                self.logger.warning(f"  File {rel_path} has a non-compliant license.")
        self.event_publisher.publish("phase_complete", phase="5.56", message="License compliance check complete")
        self.logger.info("PHASE 5.56 complete.")

        # Phase 5.6: Dependency reconciliation (requirements.txt from actual imports)
        self.logger.info("PHASE 5.6: Reconciling dependency files with actual imports...")
        self.event_publisher.publish("phase_start", phase="5.6", message="Starting dependency reconciliation")
        files = self._reconcile_requirements(files, project_root, python_version)
        self.event_publisher.publish("phase_complete", phase="5.6", message="Dependency reconciliation complete")
        self.logger.info("PHASE 5.6 complete.")

        # IMPROVED Phase 5.7: Multi-Language Test Generation and Execution
        self.logger.info("PHASE 5.7: Generating and executing tests (multi-language)...")
        self.event_publisher.publish("phase_start", phase="5.7", message="Starting multi-language test generation")
        
        # Group files by language
        files_by_language = self._group_files_by_language(files)
        generated_test_files: Dict[str, str] = {}
        test_file_paths: List[Path] = []
        
        # Generate tests for each language
        for language, lang_files in files_by_language.items():
            self.logger.info(f"  Generating {language} tests for {len(lang_files)} files...")
            
            for rel_path, content in lang_files:
                if "test" in rel_path.lower():
                    continue  # Skip test files
                
                self.event_publisher.publish("tool_start", tool_name="generate_test", file=rel_path, language=language)
                
                try:
                    test_content = self.test_generator.generate_tests(rel_path, content, readme)
                    if test_content:
                        # Determine test file path based on language
                        test_rel_path = self._get_test_file_path(rel_path, language)
                        generated_test_files[test_rel_path] = test_content
                        self._save_file(project_root / test_rel_path, test_content)
                        test_file_paths.append(project_root / test_rel_path)
                        self.event_publisher.publish("tool_output", tool_name="generate_test", file=rel_path, status="success", test_file=test_rel_path)
                    else:
                        self.event_publisher.publish("tool_output", tool_name="generate_test", file=rel_path, status="failed")
                
                except Exception as e:
                    self.logger.error(f"Error generating tests for {rel_path}: {e}")
                    self.error_kb.record_error(rel_path, "test_generation", str(e), content, readme[:500])
                    self.event_publisher.publish("tool_output", tool_name="generate_test", file=rel_path, status="error", message=str(e))
                
                self.event_publisher.publish("tool_end", tool_name="generate_test", file=rel_path)
        
        # Generate integration tests if applicable
        if len(files_by_language) > 1 or any(lang in files_by_language for lang in ["javascript", "go", "java"]):
            self.logger.info("  Generating integration tests...")
            integration_test_content, docker_compose_content = self.test_generator.generate_integration_tests(
                project_root, readme
            )
            
            if integration_test_content:
                integration_test_path = project_root / "tests" / "integration_tests.py"
                integration_test_path.parent.mkdir(parents=True, exist_ok=True)
                self._save_file(integration_test_path, integration_test_content)
                generated_test_files[str(integration_test_path.relative_to(project_root))] = integration_test_content
                self.logger.info("  Integration tests generated")
            
            if docker_compose_content:
                docker_compose_path = project_root / "docker-compose.test.yml"
                self._save_file(docker_compose_path, docker_compose_content)
                self.logger.info("  Test orchestration file generated")
        
        # Execute tests with retry logic
        if test_file_paths:
            test_retries = 0
            max_test_retries = 3
            test_results = None
            
            while test_retries < max_test_retries:
                self.logger.info(f"  Executing tests (Attempt {test_retries + 1}/{max_test_retries})...")
                self.event_publisher.publish("tool_start", tool_name="execute_tests", attempt=test_retries + 1)
                
                # Detect test framework from test files
                primary_language = max(files_by_language.keys(), key=lambda x: len(files_by_language[x]))
                test_results = self.test_generator.execute_tests(
                    project_root, test_file_paths, language=primary_language
                )
                
                if test_results["success"]:
                    self.logger.info("  All tests passed!")
                    self.event_publisher.publish("tool_output", tool_name="execute_tests", status="success", message="All tests passed")
                    self.event_publisher.publish("tool_end", tool_name="execute_tests")
                    break
                else:
                    self.logger.warning(f"  Tests failed. Failures: {len(test_results['failures'])}")
                    self.event_publisher.publish("tool_output", tool_name="execute_tests", status="failed", failures=test_results.get("failures", []))
                    self.event_publisher.publish("tool_end", tool_name="execute_tests")
                    
                    # Refine based on failures
                    if test_results.get("failures"):
                        self.logger.info("  Attempting to refine code based on test failures...")
                        self.event_publisher.publish("phase_start", phase="5.7.1", message="Refining code based on test failures")
                        
                        for failure in test_results["failures"][:5]:
                            failed_file = failure.get("path") or failure.get("name")
                            if failed_file:
                                # Find matching file
                                for rel_path in files.keys():
                                    if failed_file in rel_path or rel_path in failed_file:
                                        try:
                                            self.event_publisher.publish("tool_start", tool_name="refine_code_from_test_failure", file=rel_path)
                                            issues = [{
                                                "description": f"Test failed: {failure.get('message', '')}",
                                                "severity": "critical",
                                                "recommendation": "Fix the code to pass the test.",
                                                "context": failure.get('context', '')
                                            }]
                                            refined_content = self.refiner.refine_file(
                                                rel_path, files[rel_path], readme[:2000], issues
                                            )
                                            if refined_content:
                                                files[rel_path] = refined_content
                                                self._save_file(project_root / rel_path, refined_content)
                                                self.event_publisher.publish("tool_output", tool_name="refine_code_from_test_failure", file=rel_path, status="success")
                                            self.event_publisher.publish("tool_end", tool_name="refine_code_from_test_failure", file=rel_path)
                                            break
                                        except Exception as e:
                                            self.logger.error(f"Error refining {rel_path}: {e}")
                        
                        self.event_publisher.publish("phase_complete", phase="5.7.1", message="Refinement complete")
                    
                    test_retries += 1
            
            if test_results and not test_results["success"]:
                self.logger.warning("Tests failed after retries. Continuing with project...")
        else:
            self.logger.info("  No test files generated.")
        
        self.event_publisher.publish("phase_complete", phase="5.7", message="Test generation complete")
        self.logger.info("PHASE 5.7 complete.")

        # Phase 6: Final review
        self.logger.info("PHASE 6: Final review...")
        self.event_publisher.publish("phase_start", phase="6", message="Starting final review")
        validation_summary = self.completeness_checker.get_validation_summary(files)
        try:
            review = self.reviewer.review(project_name, readme[:500], file_paths, validation_summary)
            self._save_file(project_root / "PROJECT_REVIEW.md", review)
            self.event_publisher.publish("phase_complete", phase="6", message="Final review complete", data={"review_summary": review[:200]})
        except Exception as e:
            self.logger.error(f"  Error during review: {e}")
            self.event_publisher.publish("phase_complete", phase="6", message="Final review failed", status="error", error=str(e))


        # New Iterative Improvement Phase (Phase 7)
        if num_refine_loops > 0:
            self.logger.info(f"PHASE 7: Starting Iterative Improvement Loops ({num_refine_loops} loops)...")
            self.event_publisher.publish("phase_start", phase="7", message=f"Starting iterative improvement loops ({num_refine_loops} loops)")
            for loop_num in range(num_refine_loops):
                self.logger.info(f"PHASE 7: Iteration {loop_num + 1}/{num_refine_loops}")
                self.event_publisher.publish("iteration_start", phase="7", iteration=loop_num + 1)

                # 1. Suggest improvements
                self.event_publisher.publish("tool_start", tool_name="suggest_improvements", iteration=loop_num + 1)
                suggestions = self.suggester.suggest_improvements(
                    project_description, readme, structure, files, loop_num
                )
                self.logger.info(f"  Suggested Improvements ({len(suggestions)}): {', '.join(suggestions[:3])}...")
                self.event_publisher.publish("tool_output", tool_name="suggest_improvements", suggestions=suggestions)
                self.event_publisher.publish("tool_end", tool_name="suggest_improvements")
                if not suggestions:
                    self.logger.info("  No further improvements suggested. Ending refinement loops.")
                    self.event_publisher.publish("iteration_end", phase="7", iteration=loop_num + 1, message="No further improvements suggested")
                    break

                # 2. Plan improvements
                self.event_publisher.publish("tool_start", tool_name="plan_improvements", iteration=loop_num + 1)
                plan = self.improvement_planner.generate_plan(
                    suggestions, project_description, readme, structure, files
                )
                if not plan or not plan.get("actions"):
                    self.logger.warning("  Improvement plan could not be generated or was empty. Skipping this iteration.")
                    self.event_publisher.publish("tool_output", tool_name="plan_improvements", status="failed", message="Improvement plan empty")
                    self.event_publisher.publish("tool_end", tool_name="plan_improvements")
                    self.event_publisher.publish("iteration_end", phase="7", iteration=loop_num + 1, status="skipped")
                    continue
                self.logger.info(f"  Improvement Plan generated with {len(plan.get('actions', []))} actions.")
                self.event_publisher.publish("tool_output", tool_name="plan_improvements", status="success", plan=plan)
                self.event_publisher.publish("tool_end", tool_name="plan_improvements")

                # 3. Implement improvements
                self.event_publisher.publish("tool_start", tool_name="implement_plan", iteration=loop_num + 1)
                self.logger.info("  Implementing plan...")
                files, structure, file_paths = self._implement_plan(
                    plan, project_root, readme, structure, files, file_paths
                )
                self.event_publisher.publish("tool_output", tool_name="implement_plan", status="success", files_updated=len(files))
                self.event_publisher.publish("tool_end", tool_name="implement_plan")

                # Re-run refinement and verification after each loop to ensure quality
                self.logger.info(f"  Re-running Phase 5: Refinement after improvement loop {loop_num + 1}...")
                self.event_publisher.publish("phase_start", phase="5_rerun", iteration=loop_num + 1, message="Re-running Refinement")
                for idx, (rel_path, content) in enumerate(list(files.items()), 1):
                    if not content or len(content) < 10:
                        continue
                    self.event_publisher.publish("tool_start", tool_name="file_refinement", file=rel_path, progress=f"{idx}/{len(file_paths)}", iteration=loop_num + 1)
                    self.logger.info(f"    Refining {rel_path}")
                    try:
                        refined = self.refiner.refine_file(rel_path, content, readme[:1000])
                        if refined:
                            files[rel_path] = refined
                            self._save_file(project_root / rel_path, refined)
                            self.event_publisher.publish("tool_output", tool_name="file_refinement", file=rel_path, status="success")
                        else:
                            self.event_publisher.publish("tool_output", tool_name="file_refinement", file=rel_path, status="skipped", message="Refinement not significant")
                    except Exception as e:
                        self.logger.error(f"    Error refining {rel_path}: {e}")
                        self.event_publisher.publish("tool_output", tool_name="file_refinement", file=rel_path, status="error", message=str(e))
                    self.event_publisher.publish("tool_end", tool_name="file_refinement", file=rel_path)
                self.event_publisher.publish("phase_complete", phase="5_rerun", iteration=loop_num + 1, message="Refinement re-run complete")

                self.logger.info(f"  Re-running Phase 5.5: Verification after improvement loop {loop_num + 1}...")
                self.event_publisher.publish("phase_start", phase="5.5_rerun", iteration=loop_num + 1, message="Re-running Verification")
                files = self.completeness_checker.verify_and_fix(files, readme[:1000])
                for rel_path, content in files.items():
                    if content:
                        self._save_file(project_root / rel_path, content)
                self.event_publisher.publish("phase_complete", phase="5.5_rerun", iteration=loop_num + 1, message="Verification re-run complete")
                self.event_publisher.publish("iteration_end", phase="7", iteration=loop_num + 1, status="complete")

            self.event_publisher.publish("phase_complete", phase="7", message="Iterative Improvement complete")
            self.logger.info("PHASE 7: Iterative Improvement complete.")
        
        # Phase 7.5: Content completeness check
        self.logger.info("PHASE 7.5: Checking content completeness (placeholder detection)...")
        self.event_publisher.publish("phase_start", phase="7.5", message="Checking content completeness")
        incomplete_files = []
        for rel_path, content in files.items():
            if not content:
                continue
            warning = self.file_validator.check_content_completeness(rel_path, content)
            if warning:
                self.logger.warning(f"  INCOMPLETE: {rel_path} — {warning}")
                incomplete_files.append(rel_path)

        if incomplete_files:
            self.logger.info(f"  Found {len(incomplete_files)} incomplete files, attempting to complete them...")
            self.event_publisher.publish("tool_start", tool_name="complete_incomplete_files", count=len(incomplete_files))
            for rel_path in incomplete_files:
                content = files[rel_path]
                try:
                    issues = [{"description": "File contains placeholder/stub content that needs real implementation",
                               "severity": "major",
                               "recommendation": "Replace all TODO, placeholder, and stub content with real implementations"}]
                    refined = self.refiner.refine_file(rel_path, content, readme[:2000], issues)
                    if refined:
                        files[rel_path] = refined
                        self._save_file(project_root / rel_path, refined)
                        self.logger.info(f"    Completed: {rel_path}")
                        self.event_publisher.publish("tool_output", tool_name="complete_incomplete_files", file=rel_path, status="success")
                except Exception as e:
                    self.logger.error(f"    Error completing {rel_path}: {e}")
                    self.event_publisher.publish("tool_output", tool_name="complete_incomplete_files", file=rel_path, status="error", message=str(e))

            # Re-verify after completing
            files = self.completeness_checker.verify_and_fix(files, readme[:2000])
            for rel_path, content in files.items():
                if content:
                    self._save_file(project_root / rel_path, content)
            self.event_publisher.publish("tool_end", tool_name="complete_incomplete_files")

        self.event_publisher.publish("phase_complete", phase="7.5", message="Content completeness check complete")
        self.logger.info("PHASE 7.5 complete.")

        # Senior Review Phase (Phase 8)
        self.logger.info("PHASE 8: Starting Senior Review...")
        self.event_publisher.publish("phase_start", phase="8", message="Starting Senior Review")
        review_passed = False
        review_attempt = 0
        max_review_attempts = 3
        while not review_passed and review_attempt < max_review_attempts:
            review_attempt += 1
            self.logger.info(f"PHASE 8: Senior Review Attempt {review_attempt}/{max_review_attempts}...")
            self.event_publisher.publish("tool_start", tool_name="senior_review", attempt=review_attempt)

            review_results = self.senior_reviewer.perform_review(
                project_description, project_name, readme, structure, files, review_attempt
            )

            if review_results.get("status") == "passed":
                review_passed = True
                self.logger.info("PHASE 8: Senior Review Passed!")
                self._save_file(project_root / "SENIOR_REVIEW_SUMMARY.md", review_results.get("summary", "Senior review passed."))
                self.event_publisher.publish("tool_output", tool_name="senior_review", status="passed", summary=review_results.get("summary"))
            else:
                issues = review_results.get("issues", [])
                self.logger.warning(f"PHASE 8: Senior Review Failed. Issues found: {len(issues)}")
                self.event_publisher.publish("tool_output", tool_name="senior_review", status="failed", issues=issues)

                # Save detailed issue log
                issue_log = f"# Senior Review Issues — Attempt {review_attempt}\n\n"
                issue_log += f"**Summary:** {review_results.get('summary', 'N/A')}\n\n"
                for i, issue in enumerate(issues, 1):
                    issue_log += (
                        f"## Issue {i}: [{issue.get('severity', 'unknown').upper()}]\n"
                        f"**File:** {issue.get('file', 'N/A')}\n"
                        f"**Description:** {issue.get('description', 'N/A')}\n"
                        f"**Recommendation:** {issue.get('recommendation', 'N/A')}\n\n"
                    )
                self._save_file(project_root / f"SENIOR_REVIEW_ISSUES_ATTEMPT_{review_attempt}.md", issue_log)

                if issues:
                    self.logger.info("  Attempting targeted fixes based on senior review issues...")
                    self.event_publisher.publish("tool_start", tool_name="fix_senior_review_issues", count=len(issues))

                    contingency_plan = self.contingency_planner.generate_contingency_plan(issues, project_description, readme)
                    if contingency_plan and contingency_plan.get("actions"):
                        self.logger.info("  Contingency plan generated. Implementing...")
                        files, structure, file_paths = self._implement_plan(
                            contingency_plan, project_root, readme, structure, files, file_paths
                        )
                    else:
                        # Fallback to simple refinement
                        files_with_issues = set()
                        general_issues = []
                        for issue in issues:
                            file_value = issue.get("file")
                            if file_value:
                                if isinstance(file_value, list):
                                    file_value = str(file_value)
                                    self.logger.warning(f"  Senior Review: 'file' field was a list, converted to string: {file_value}")
                                files_with_issues.add(file_value)
                            else:
                                general_issues.append(issue)

                        # Fix files that have specific issues
                        for rel_path in files_with_issues:
                            if rel_path not in files or not files[rel_path] or len(files[rel_path]) < 10:
                                continue
                            self.logger.info(f"    Fixing {rel_path} (targeted)...")
                            self.event_publisher.publish("tool_start", tool_name="refine_from_senior_review", file=rel_path)
                            try:
                                file_issues = [iss for iss in issues if iss.get("file") == rel_path]
                                refined = self.refiner.refine_file(
                                    rel_path, files[rel_path], readme[:2000], file_issues
                                )
                                if refined:
                                    files[rel_path] = refined
                                    self._save_file(project_root / rel_path, refined)
                                    self.event_publisher.publish("tool_output", tool_name="refine_from_senior_review", file=rel_path, status="success")
                                else:
                                    self.logger.warning(f"    Refiner failed to improve {rel_path}.")
                                    self.event_publisher.publish("tool_output", tool_name="refine_from_senior_review", file=rel_path, status="failed", message="Refiner failed")
                            except Exception as e:
                                self.logger.error(f"    Error fixing {rel_path}: {e}")
                                self.event_publisher.publish("tool_output", tool_name="refine_from_senior_review", file=rel_path, status="error", message=str(e))
                            self.event_publisher.publish("tool_end", tool_name="refine_from_senior_review", file=rel_path)

                        # For general issues without a specific file, refine all non-trivial files
                        if general_issues:
                            self.logger.info(f"  Applying {len(general_issues)} general fixes across all files...")
                            for rel_path, content in list(files.items()):
                                if not content or len(content) < 10 or rel_path in files_with_issues:
                                    continue
                                self.event_publisher.publish("tool_start", tool_name="refine_from_senior_review_general", file=rel_path)
                                try:
                                    refined = self.refiner.refine_file(
                                        rel_path, content, readme[:2000], general_issues
                                    )
                                    if refined:
                                        files[rel_path] = refined
                                        self._save_file(project_root / rel_path, refined)
                                        self.event_publisher.publish("tool_output", tool_name="refine_from_senior_review_general", file=rel_path, status="success")
                                    else:
                                        self.logger.warning(f"    Refiner failed to improve {rel_path}.")
                                        self.event_publisher.publish("tool_output", tool_name="refine_from_senior_review_general", file=rel_path, status="failed", message="Refiner failed")
                                except Exception as e:
                                    self.logger.error(f"    Error refining {rel_path}: {e}")
                                    self.event_publisher.publish("tool_output", tool_name="refine_from_senior_review_general", file=rel_path, status="error", message=str(e))
                                self.event_publisher.publish("tool_end", tool_name="refine_from_senior_review_general", file=rel_path)
                        self.event_publisher.publish("tool_end", tool_name="fix_senior_review_issues")

                    self.logger.info("  Re-running verification after senior review fixes...")
                    files = self.completeness_checker.verify_and_fix(files, readme[:2000])
                    for rel_path, content in files.items():
                        if content:
                            self._save_file(project_root / rel_path, content)
                else:
                    self.logger.warning("  No specific issues provided by senior reviewer to fix.")
            self.event_publisher.publish("tool_end", tool_name="senior_review")

        if not review_passed:
            self.logger.error("PHASE 8: Senior Review failed after multiple attempts. Manual intervention may be required.")
            self._save_file(project_root / "SENIOR_REVIEW_FAILED.md", "Senior review failed after multiple attempts.")
            self.event_publisher.publish("phase_complete", phase="8", message="Senior Review failed", status="error")
        else:
            self.event_publisher.publish("phase_complete", phase="8", message="Senior Review complete", status="success")
        
        self.logger.info(f"Project '{project_name}' completed at {project_root}")
        self.event_publisher.publish("project_complete", project_name=project_name, project_root=str(project_root), files_generated=len(file_paths))
        
        # Log knowledge base statistics
        kb_stats = self.error_kb.get_error_statistics()
        self.logger.info(f"Knowledge Base Stats: {kb_stats}")
        
        # Log fragment cache statistics  
        cache_stats = self.fragment_cache.stats()
        self.logger.info(f"Fragment Cache Stats: {cache_stats}")
        
        return project_root
    
    # ========== NEW HELPER METHODS FOR IMPROVED FEATURES ==========
    
    def _infer_language(self, file_path: str) -> str:
        """Infer programming language from file path."""
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
    
    def _group_files_by_language(self, files: Dict[str, str]) -> Dict[str, List[Tuple[str, str]]]:
        """Group files by programming language."""
        grouped = defaultdict(list)
        
        for rel_path, content in files.items():
            language = self._infer_language(rel_path)
            if language != "unknown":
                grouped[language].append((rel_path, content))
        
        return dict(grouped)
    
    def _get_test_file_path(self, source_file: str, language: str) -> str:
        """Get test file path based on language conventions."""
        source_path = Path(source_file)
        
        # Language-specific test path patterns
        patterns = {
            "python": lambda p: str(Path("tests") / f"test_{p}.py"),
            "javascript": lambda p: str(Path("tests") / f"{p}.test.js"),
            "typescript": lambda p: str(Path("tests") / f"{p}.test.ts"),
            "go": lambda p: str(Path(p).parent / f"{p}_test.go"),
            "rust": lambda p: str(Path("tests") / f"{p}.rs"),
            "java": lambda p: str(Path("src/test/java") / f"{p}Test.java"),
        }
        
        stem = source_path.stem
        pattern_fn = patterns.get(language, lambda p: str(Path("tests") / f"test_{p}"))
        return pattern_fn(stem)
    
    def _implement_plan(
        self,
        plan: Dict,
        project_root: Path,
        readme: str,
        structure: Dict,
        files: Dict[str, str],
        file_paths: List[str]
    ) -> Tuple[Dict[str, str], Dict, List[str]]:
        """Implement contingency plan from planner."""
        actions = plan.get("actions", [])
        self.logger.info(f"Implementing {len(actions)} contingency actions...")
        
        for action in actions[:10]:  # Limit to 10 actions
            action_type = action.get("type")
            
            if action_type == "create_file":
                target_path = action.get("path")
                content = action.get("content", "")
                if target_path:
                    files[target_path] = content
                    self._save_file(project_root / target_path, content)
                    if target_path not in file_paths:
                        file_paths.append(target_path)
            
            elif action_type == "modify_file":
                target_path = action.get("path")
                changes = action.get("changes", {})
                if target_path and target_path in files:
                    content = files[target_path]
                    # Simple text replacement for changes
                    for old_text, new_text in changes.items():
                        content = content.replace(old_text, new_text)
                    files[target_path] = content
                    self._save_file(project_root / target_path, content)
            
            elif action_type == "refine_file":
                target_path = action.get("path")
                issues = action.get("issues", [])
                if target_path and target_path in files:
                    try:
                        refined = self.refiner.refine_file(target_path, files[target_path], readme[:2000], issues)
                        if refined:
                            files[target_path] = refined
                            self._save_file(project_root / target_path, refined)
                    except Exception as e:
                        self.logger.error(f"Error refining {target_path}: {e}")
        
        return files, structure, file_paths