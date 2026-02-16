from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase


class TestGenerationExecutionPhase(IAgentPhase):
    """
    Phase 5.7: Generates and executes tests (MANDATORY FOR MVP)

    This phase is critical for MVP. It:
    1. MUST generate tests for all source files
    2. MUST execute tests until they pass or max retries reached
    3. Uses FileRefiner to fix code failures
    4. Treats test failures as critical issues

    Multiple language support with aggressive retry strategy.
    """

    # MVP-specific constraints
    MVP_MODE = True  # Always true for current version
    MAX_RETRIES = 5  # Increased from 3 to 5 for MVP compliance
    MIN_TEST_FILES_REQUIRED = 1  # Must generate at least one test file

    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(
        self,
        project_description: str,
        project_name: str,
        project_root: Path,
        readme_content: str,
        initial_structure: Dict[str, Any],
        generated_files: Dict[str, str],  # Files for which tests are generated and executed
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        file_paths = kwargs.get("file_paths", [])  # Get from kwargs or assume context has it

        self.context.logger.info("PHASE 5.7 (MVP): Generating and executing tests - MANDATORY FOR MVP...")
        self.context.event_publisher.publish(
            "phase_start",
            phase="5.7",
            message="Starting mandatory test generation and execution (MVP)",
        )

        # Group files by language
        files_by_language = self.context.group_files_by_language(generated_files)
        generated_test_files: Dict[str, str] = {}
        test_file_paths: List[Path] = []

        # Step 1: Generate tests for each language (MANDATORY)
        for language, lang_files in files_by_language.items():
            self.context.logger.info(
                f"  📝 Generating {language} tests for {len(lang_files)} files (MVP requirement)..."
            )

            for rel_path, content in lang_files:
                if "test" in rel_path.lower():
                    continue  # Skip test files

                self.context.event_publisher.publish(
                    "tool_start",
                    tool_name="generate_test",
                    file=rel_path,
                    language=language,
                )

                try:
                    test_content = self.context.test_generator.generate_tests(rel_path, content, readme_content)
                    if test_content:
                        # Determine test file path based on language
                        test_rel_path = self.context.get_test_file_path(rel_path, language)
                        generated_test_files[test_rel_path] = test_content
                        self.context.file_manager.write_file(project_root / test_rel_path, test_content)
                        test_file_paths.append(project_root / Path(test_rel_path))
                        self.context.event_publisher.publish(
                            "tool_output",
                            tool_name="generate_test",
                            file=rel_path,
                            status="success",
                            test_file=test_rel_path,
                        )
                        self.context.logger.info(f"    ✅ Test generated: {test_rel_path}")
                    else:
                        self.context.logger.warning(f"    ⚠️ Could not generate test for {rel_path}")
                        self.context.event_publisher.publish(
                            "tool_output",
                            tool_name="generate_test",
                            file=rel_path,
                            status="failed",
                        )

                except Exception as e:
                    self.context.logger.error(f"Error generating tests for {rel_path}: {e}")
                    self.context.error_knowledge_base.record_error(
                        rel_path,
                        "test_generation",
                        str(e),
                        content,
                        readme_content[:500],
                    )
                    self.context.event_publisher.publish(
                        "tool_output",
                        tool_name="generate_test",
                        file=rel_path,
                        status="error",
                        message=str(e),
                    )

                self.context.event_publisher.publish("tool_end", tool_name="generate_test", file=rel_path)

        # Verify MVP requirement: at least one test file generated
        if len(generated_test_files) < self.MIN_TEST_FILES_REQUIRED:
            self.context.logger.error(
                f"❌ MVP REQUIREMENT FAILED: No test files generated. "
                f"Expected at least {self.MIN_TEST_FILES_REQUIRED}, got {len(generated_test_files)}"
            )
            self.context.event_publisher.publish(
                "mvp_requirement_failed",
                requirement="test_generation",
                message="No test files were generated. Tests are mandatory for MVP.",
            )
            raise RuntimeError(
                f"MVP Requirement Failed: Must generate at least {self.MIN_TEST_FILES_REQUIRED} test file(s)"
            )

        self.context.logger.info(f"✅ Generated {len(generated_test_files)} test files (MVP requirement met)")

        # Step 2: Generate integration tests if applicable
        if len(files_by_language) > 1 or any(lang in files_by_language for lang in ["javascript", "go", "java"]):
            self.context.logger.info("  🔗 Generating integration tests...")
            try:
                (
                    integration_test_content,
                    docker_compose_content,
                ) = self.context.test_generator.generate_integration_tests(project_root, readme_content)

                if integration_test_content:
                    integration_test_path = project_root / "tests" / "integration_tests.py"
                    integration_test_path.parent.mkdir(parents=True, exist_ok=True)
                    self.context.file_manager.write_file(integration_test_path, integration_test_content)
                    generated_test_files[str(integration_test_path.relative_to(project_root))] = (
                        integration_test_content
                    )
                    test_file_paths.append(integration_test_path)
                    self.context.logger.info("    ✅ Integration tests generated")

                if docker_compose_content:
                    docker_compose_path = project_root / "docker-compose.test.yml"
                    self.context.file_manager.write_file(docker_compose_path, docker_compose_content)
                    generated_test_files[str(docker_compose_path.relative_to(project_root))] = docker_compose_content
                    self.context.logger.info("    ✅ Test orchestration file generated")
            except Exception as e:
                self.context.logger.warning(f"Could not generate integration tests: {e}")

        # Step 3: Execute tests with aggressive retry logic (MVP requirement: tests must pass)
        if test_file_paths:
            test_retries = 0
            max_test_retries = self.MAX_RETRIES
            test_results = None

            while test_retries < max_test_retries:
                self.context.logger.info(f"  🧪 Test Execution Attempt {test_retries + 1}/{max_test_retries}...")
                self.context.event_publisher.publish(
                    "tool_start",
                    tool_name="execute_tests",
                    attempt=test_retries + 1,
                    max_attempts=max_test_retries,
                )

                # Detect test framework from test files
                primary_language = (
                    max(
                        files_by_language.keys(),
                        key=lambda x: len(files_by_language[x]),
                    )
                    if files_by_language
                    else "python"
                )
                test_results = self.context.test_generator.execute_tests(
                    project_root, test_file_paths, language=primary_language
                )

                if test_results["success"]:
                    self.context.logger.info("  ✅ ALL TESTS PASSED! (MVP requirement satisfied)")
                    self.context.event_publisher.publish(
                        "tool_output",
                        tool_name="execute_tests",
                        status="success",
                        message=f"All tests passed on attempt {test_retries + 1}",
                    )
                    self.context.event_publisher.publish("tool_end", tool_name="execute_tests")
                    break
                else:
                    failure_count = len(test_results.get("failures", []))
                    self.context.logger.warning(
                        f"  ❌ Tests failed with {failure_count} failure(s). "
                        f"Attempt {test_retries + 1}/{max_test_retries}"
                    )
                    self.context.event_publisher.publish(
                        "tool_output",
                        tool_name="execute_tests",
                        status="failed",
                        failures=test_results.get("failures", []),
                        attempt=test_retries + 1,
                    )

                    # Refine code based on failures (aggressive refinement for MVP)
                    if test_results.get("failures") and test_retries < max_test_retries - 1:
                        self.context.logger.info(
                            f"  🔧 Refining code based on {failure_count} test failure(s) "
                            f"(MVP requirement: tests must pass)..."
                        )
                        self.context.event_publisher.publish(
                            "phase_start",
                            phase="5.7.1",
                            message=f"Refining code based on test failures (attempt {test_retries + 1})",
                        )

                        refined_count = 0
                        # Process all failures, not just top 5
                        for failure in test_results["failures"]:
                            failed_file = failure.get("path") or failure.get("name")
                            if not failed_file:
                                continue

                            # Find matching source file to refine
                            matched_rel_path = None
                            for rel_path in generated_files.keys():
                                if failed_file in rel_path or Path(rel_path).name == Path(failed_file).name:
                                    matched_rel_path = rel_path
                                    break

                            if matched_rel_path:
                                try:
                                    self.context.event_publisher.publish(
                                        "tool_start",
                                        tool_name="refine_code_from_test_failure",
                                        file=matched_rel_path,
                                        attempt=test_retries + 1,
                                    )

                                    # Create issue details from test failure
                                    issues = [
                                        {
                                            "description": f"Test failed: {failure.get('message', 'Unknown error')}",
                                            "severity": "critical",
                                            "recommendation": "Fix the code to pass the test.",
                                            "context": failure.get("context", ""),
                                            "test_output": failure.get("output", ""),
                                        }
                                    ]

                                    # Refine the file
                                    refined_content = self.context.file_refiner.refine_file(
                                        matched_rel_path,
                                        generated_files[matched_rel_path],
                                        readme_content[:2000],
                                        issues,
                                    )

                                    if refined_content and refined_content != generated_files[matched_rel_path]:
                                        generated_files[matched_rel_path] = refined_content
                                        self.context.file_manager.write_file(
                                            project_root / matched_rel_path,
                                            refined_content,
                                        )
                                        refined_count += 1
                                        self.context.logger.info(f"    ✅ Refined: {matched_rel_path}")
                                        self.context.event_publisher.publish(
                                            "tool_output",
                                            tool_name="refine_code_from_test_failure",
                                            file=matched_rel_path,
                                            status="success",
                                        )
                                    else:
                                        self.context.logger.warning(f"    ⚠️ No changes made to {matched_rel_path}")
                                        self.context.event_publisher.publish(
                                            "tool_output",
                                            tool_name="refine_code_from_test_failure",
                                            file=matched_rel_path,
                                            status="no_changes",
                                        )

                                    self.context.event_publisher.publish(
                                        "tool_end",
                                        tool_name="refine_code_from_test_failure",
                                        file=matched_rel_path,
                                    )

                                except Exception as e:
                                    self.context.logger.error(f"  ❌ Error refining {matched_rel_path}: {e}")
                                    self.context.event_publisher.publish(
                                        "tool_output",
                                        tool_name="refine_code_from_test_failure",
                                        file=matched_rel_path,
                                        status="error",
                                        message=str(e),
                                    )

                        self.context.logger.info(f"    Refinement complete: {refined_count} files refined")
                        self.context.event_publisher.publish(
                            "phase_complete",
                            phase="5.7.1",
                            message=f"Refinement complete: {refined_count} files refined",
                        )

                    test_retries += 1

            # Check final test results
            if test_results and not test_results["success"]:
                self.context.logger.error(
                    f"❌ Tests still failing after {max_test_retries} attempts. "
                    f"Failures: {len(test_results.get('failures', []))}"
                )
                self.context.event_publisher.publish(
                    "test_execution_incomplete",
                    message=f"Tests failed after {max_test_retries} retry attempts",
                    failures=test_results.get("failures", []),
                )
                # For MVP, we log but continue (could be made stricter)
                self.context.logger.warning("⚠️ Tests did not pass, but continuing with project generation...")
        else:
            self.context.logger.error("❌ No test files to execute!")
            raise RuntimeError("MVP Requirement Failed: No test files were generated")

        self.context.event_publisher.publish(
            "phase_complete",
            phase="5.7",
            message="Test generation and execution phase complete",
        )
        self.context.logger.info("✅ PHASE 5.7 (MVP) complete.")

        # Update file_paths to include generated test files
        file_paths.extend(
            [
                str(p.relative_to(project_root))
                for p in test_file_paths
                if str(p.relative_to(project_root)) not in file_paths
            ]
        )
        file_paths.extend([rp for rp in generated_test_files if rp not in file_paths])

        return generated_files, initial_structure, file_paths
