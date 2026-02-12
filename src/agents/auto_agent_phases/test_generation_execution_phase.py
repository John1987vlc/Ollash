from typing import Dict, Any, List, Tuple
from pathlib import Path
from collections import defaultdict

from src.interfaces.iagent_phase import IAgentPhase
from src.agents.auto_agent_phases.phase_context import PhaseContext
from src.utils.domains.auto_generation.structure_generator import StructureGenerator # For extract_file_paths


class TestGenerationExecutionPhase(IAgentPhase):
    """
    Phase 5.7: Generates tests for the developed code (multi-language support)
    and executes them, attempting to fix code based on test failures.
    """
    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(self,
                      project_description: str,
                      project_name: str,
                      project_root: Path,
                      readme_content: str,
                      initial_structure: Dict[str, Any],
                      generated_files: Dict[str, str], # Files for which tests are generated and executed
                      **kwargs: Any) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        
        file_paths = kwargs.get("file_paths", []) # Get from kwargs or assume context has it
        
        self.context.logger.info("PHASE 5.7: Generating and executing tests (multi-language)...")
        self.context.event_publisher.publish("phase_start", phase="5.7", message="Starting multi-language test generation")
        
        # Group files by language
        files_by_language = self.context.group_files_by_language(generated_files)
        generated_test_files: Dict[str, str] = {}
        test_file_paths: List[Path] = []
        
        # Generate tests for each language
        for language, lang_files in files_by_language.items():
            self.context.logger.info(f"  Generating {language} tests for {len(lang_files)} files...")
            
            for rel_path, content in lang_files:
                if "test" in rel_path.lower():
                    continue  # Skip test files
                
                self.context.event_publisher.publish("tool_start", tool_name="generate_test", file=rel_path, language=language)
                
                try:
                    test_content = self.context.test_generator.generate_tests(rel_path, content, readme_content)
                    if test_content:
                        # Determine test file path based on language
                        test_rel_path = self.context.get_test_file_path(rel_path, language)
                        generated_test_files[test_rel_path] = test_content
                        self.context.file_manager.write_file(project_root / test_rel_path, test_content)
                        test_file_paths.append(project_root / Path(test_rel_path)) # Path object for execution
                        self.context.event_publisher.publish("tool_output", tool_name="generate_test", file=rel_path, status="success", test_file=test_rel_path)
                    else:
                        self.context.event_publisher.publish("tool_output", tool_name="generate_test", file=rel_path, status="failed")
                
                except Exception as e:
                    self.context.logger.error(f"Error generating tests for {rel_path}: {e}")
                    self.context.error_knowledge_base.record_error(rel_path, "test_generation", str(e), content, readme_content[:500])
                    self.context.event_publisher.publish("tool_output", tool_name="generate_test", file=rel_path, status="error", message=str(e))
                
                self.context.event_publisher.publish("tool_end", tool_name="generate_test", file=rel_path)
        
        # Generate integration tests if applicable
        if len(files_by_language) > 1 or any(lang in files_by_language for lang in ["javascript", "go", "java"]):
            self.context.logger.info("  Generating integration tests...")
            integration_test_content, docker_compose_content = self.context.test_generator.generate_integration_tests(
                project_root, readme_content
            )
            
            if integration_test_content:
                integration_test_path = project_root / "tests" / "integration_tests.py"
                integration_test_path.parent.mkdir(parents=True, exist_ok=True)
                self.context.file_manager.write_file(integration_test_path, integration_test_content)
                generated_test_files[str(integration_test_path.relative_to(project_root))] = integration_test_content
                test_file_paths.append(integration_test_path)
                self.context.logger.info("  Integration tests generated")
            
            if docker_compose_content:
                docker_compose_path = project_root / "docker-compose.test.yml"
                self.context.file_manager.write_file(docker_compose_path, docker_compose_content)
                generated_test_files[str(docker_compose_path.relative_to(project_root))] = docker_compose_content
                self.context.logger.info("  Test orchestration file generated")
        
        # Execute tests with retry logic
        if test_file_paths:
            test_retries = 0
            max_test_retries = 3
            test_results = None
            
            while test_retries < max_test_retries:
                self.context.logger.info(f"  Executing tests (Attempt {test_retries + 1}/{max_test_retries})...")
                self.context.event_publisher.publish("tool_start", tool_name="execute_tests", attempt=test_retries + 1)
                
                # Detect test framework from test files
                primary_language = max(files_by_language.keys(), key=lambda x: len(files_by_language[x])) if files_by_language else "python" # Default if no files
                test_results = self.context.test_generator.execute_tests(
                    project_root, test_file_paths, language=primary_language
                )
                
                if test_results["success"]:
                    self.context.logger.info("  All tests passed!")
                    self.context.event_publisher.publish("tool_output", tool_name="execute_tests", status="success", message="All tests passed")
                    self.context.event_publisher.publish("tool_end", tool_name="execute_tests")
                    break
                else:
                    self.context.logger.warning(f"  Tests failed. Failures: {len(test_results['failures'])}")
                    self.context.event_publisher.publish("tool_output", tool_name="execute_tests", status="failed", failures=test_results.get("failures", []))
                    self.context.event_publisher.publish("tool_end", tool_name="execute_tests")
                    
                    # Refine based on failures
                    if test_results.get("failures"):
                        self.context.logger.info("  Attempting to refine code based on test failures...")
                        self.context.event_publisher.publish("phase_start", phase="5.7.1", message="Refining code based on test failures")
                        
                        for failure in test_results["failures"][:5]: # Limit to top 5 failures for refinement
                            failed_file = failure.get("path") or failure.get("name")
                            if failed_file:
                                # Find matching file
                                for rel_path in generated_files.keys():
                                    if failed_file in rel_path or Path(rel_path).name == Path(failed_file).name:
                                        try:
                                            self.context.event_publisher.publish("tool_start", tool_name="refine_code_from_test_failure", file=rel_path)
                                            issues = [{
                                                "description": f"Test failed: {failure.get('message', '')}",
                                                "severity": "critical",
                                                "recommendation": "Fix the code to pass the test.",
                                                "context": failure.get('context', '')
                                            }]
                                            refined_content = self.context.file_refiner.refine_file(
                                                rel_path, generated_files[rel_path], readme_content[:2000], issues
                                            )
                                            if refined_content:
                                                generated_files[rel_path] = refined_content
                                                self.context.file_manager.write_file(project_root / rel_path, refined_content)
                                                self.context.event_publisher.publish("tool_output", tool_name="refine_code_from_test_failure", file=rel_path, status="success")
                                            self.context.event_publisher.publish("tool_end", tool_name="refine_code_from_test_failure", file=rel_path)
                                            break
                                        except Exception as e:
                                            self.context.logger.error(f"  Error refining {rel_path}: {e}")
                                            self.context.event_publisher.publish("tool_output", tool_name="refine_code_from_test_failure", file=rel_path, status="error", message=str(e))
                        
                        self.context.event_publisher.publish("phase_complete", phase="5.7.1", message="Refinement complete")
                    
                    test_retries += 1
            
            if test_results and not test_results["success"]:
                self.context.logger.warning("Tests failed after retries. Continuing with project...")
        else:
            self.context.logger.info("  No test files generated.")
        
        self.context.event_publisher.publish("phase_complete", phase="5.7", message="Test generation complete")
        self.context.logger.info("PHASE 5.7 complete.")

        # Update file_paths to include generated test files
        file_paths.extend([str(p.relative_to(project_root)) for p in test_file_paths if p not in file_paths])
        file_paths.extend([rp for rp in generated_test_files if rp not in file_paths])


        return generated_files, initial_structure, file_paths
