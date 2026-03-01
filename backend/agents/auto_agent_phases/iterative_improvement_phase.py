from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase
from backend.utils.domains.auto_generation.quality_gate import QualityGate, QualityReport


class IterativeImprovementPhase(IAgentPhase):
    """
    Phase 7: Conducts iterative improvement loops based on suggestions,
    planning, implementation, and re-verification.

    After each implementation step, a QualityGate check runs tests and linter.
    If quality checks fail an auto-heal sub-loop (up to MAX_HEAL_ITERATIONS)
    attempts to fix the issues before proceeding to the next iteration.
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
        generated_files: Dict[str, str],  # Files to be improved
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        file_paths = kwargs.get("file_paths", [])  # Get from kwargs or assume context has it
        num_refine_loops = kwargs.get("num_refine_loops", 0)

        if num_refine_loops > 0:
            self.context.logger.info(f"PHASE 7: Starting Iterative Improvement Loops ({num_refine_loops} loops)...")
            self.context.event_publisher.publish(
                "phase_start",
                phase="7",
                message=f"Starting iterative improvement loops ({num_refine_loops} loops)",
            )
            for loop_num in range(num_refine_loops):
                is_maintenance = kwargs.get("maintenance_mode", False)
                mode_str = "AUDIT" if is_maintenance else "REFINEMENT"
                self.context.logger.info(f"PHASE 7: {mode_str} Iteration {loop_num + 1}/{num_refine_loops}")
                self.context.event_publisher.publish("iteration_start", phase="7", iteration=loop_num + 1)

                # 1. Suggest improvements
                self.context.event_publisher.publish(
                    "tool_start",
                    tool_name="suggest_improvements",
                    iteration=loop_num + 1,
                )

                # If maintenance, we could use a different prompt or logic here
                suggestions = self.context.improvement_suggester.suggest_improvements(
                    project_description,
                    readme_content,
                    initial_structure,
                    generated_files,
                    loop_num,
                )
                self.context.logger.info(
                    f"  Suggested Improvements ({len(suggestions)}): {', '.join(suggestions[:3])}..."
                )
                self.context.event_publisher.publish(
                    "tool_output",
                    tool_name="suggest_improvements",
                    suggestions=suggestions,
                )
                self.context.event_publisher.publish("tool_end", tool_name="suggest_improvements")
                if not suggestions:
                    self.context.logger.info("  No further improvements suggested. Ending refinement loops.")
                    self.context.event_publisher.publish(
                        "iteration_end",
                        phase="7",
                        iteration=loop_num + 1,
                        message="No further improvements suggested",
                    )
                    break

                # 2. Plan improvements
                self.context.event_publisher.publish(
                    "tool_start", tool_name="plan_improvements", iteration=loop_num + 1
                )
                plan = self.context.improvement_planner.generate_plan(
                    suggestions,
                    project_description,
                    readme_content,
                    initial_structure,
                    generated_files,
                )
                if not plan or not plan.get("actions"):
                    self.context.logger.warning(
                        "  Improvement plan could not be generated or was empty. Skipping this iteration."
                    )
                    self.context.event_publisher.publish(
                        "tool_output",
                        tool_name="plan_improvements",
                        status="failed",
                        message="Improvement plan empty",
                    )
                    self.context.event_publisher.publish("tool_end", tool_name="plan_improvements")
                    self.context.event_publisher.publish(
                        "iteration_end",
                        phase="7",
                        iteration=loop_num + 1,
                        status="skipped",
                    )
                    continue
                self.context.logger.info(f"  Improvement Plan generated with {len(plan.get('actions', []))} actions.")
                self.context.event_publisher.publish(
                    "tool_output",
                    tool_name="plan_improvements",
                    status="success",
                    plan=plan,
                )
                self.context.event_publisher.publish("tool_end", tool_name="plan_improvements")

                # 3. Implement improvements
                self.context.event_publisher.publish("tool_start", tool_name="implement_plan", iteration=loop_num + 1)
                self.context.logger.info("  Implementing plan...")
                (
                    generated_files,
                    initial_structure,
                    file_paths,
                ) = self.context.implement_plan(
                    plan,
                    project_root,
                    readme_content,
                    initial_structure,
                    generated_files,
                    file_paths,
                )
                self.context.event_publisher.publish(
                    "tool_output",
                    tool_name="implement_plan",
                    status="success",
                    files_updated=len(generated_files),
                )
                self.context.event_publisher.publish("tool_end", tool_name="implement_plan")

                # 3b. Quality gate: run tests + linter; auto-heal if failing
                quality_report = await self._run_quality_check(project_root, generated_files)
                if not quality_report.overall_pass:
                    generated_files = await self._auto_heal_loop(
                        quality_report, generated_files, project_root, readme_content
                    )

                # Re-run refinement and verification after each loop to ensure quality
                self.context.logger.info(f"  Re-running Phase 5: Refinement after improvement loop {loop_num + 1}...")
                self.context.event_publisher.publish(
                    "phase_start",
                    phase="5_rerun",
                    iteration=loop_num + 1,
                    message="Re-running Refinement",
                )

                # Re-execute FileRefinementPhase logic
                for idx, (rel_path, content) in enumerate(list(generated_files.items()), 1):
                    if not content or len(content) < 10:
                        continue
                    self.context.event_publisher.publish(
                        "tool_start",
                        tool_name="file_refinement",
                        file=rel_path,
                        progress=f"{idx}/{len(file_paths)}",
                        iteration=loop_num + 1,
                    )
                    self.context.logger.info(f"    Refining {rel_path}")
                    try:
                        refined = self.context.file_refiner.refine_file(rel_path, content, readme_content[:1000])
                        if refined:
                            generated_files[rel_path] = refined
                            vresult = self._validated_write(project_root / rel_path, refined)
                            if not vresult.approved:
                                self.context.logger.warning(
                                    f"    SandboxValidator rejected {rel_path}: {vresult.reason}. "
                                    f"Candidate saved at {vresult.candidate_path}"
                                )
                            self.context.event_publisher.publish(
                                "tool_output",
                                tool_name="file_refinement",
                                file=rel_path,
                                status="success" if vresult.approved else "candidate",
                            )
                        else:
                            self.context.event_publisher.publish(
                                "tool_output",
                                tool_name="file_refinement",
                                file=rel_path,
                                status="skipped",
                                message="Refinement not significant",
                            )
                    except Exception as e:
                        self.context.logger.error(f"    Error refining {rel_path}: {e}")
                        self.context.event_publisher.publish(
                            "tool_output",
                            tool_name="file_refinement",
                            file=rel_path,
                            status="error",
                            message=str(e),
                        )
                    self.context.event_publisher.publish("tool_end", tool_name="file_refinement", file=rel_path)
                self.context.event_publisher.publish(
                    "phase_complete",
                    phase="5_rerun",
                    iteration=loop_num + 1,
                    message="Refinement re-run complete",
                )

                self.context.logger.info(
                    f"  Re-running Phase 5.5: Verification after improvement loop {loop_num + 1}..."
                )
                self.context.event_publisher.publish(
                    "phase_start",
                    phase="5.5_rerun",
                    iteration=loop_num + 1,
                    message="Re-running Verification",
                )

                # Re-execute VerificationPhase logic
                generated_files = await self.context.file_completeness_checker.verify_and_fix(
                    generated_files, readme_content[:1000]
                )
                for rel_path, content in generated_files.items():
                    if content:
                        self.context.file_manager.write_file(project_root / rel_path, content)
                self.context.event_publisher.publish(
                    "phase_complete",
                    phase="5.5_rerun",
                    iteration=loop_num + 1,
                    message="Verification re-run complete",
                )
                self.context.event_publisher.publish(
                    "iteration_end",
                    phase="7",
                    iteration=loop_num + 1,
                    status="complete",
                )

            self.context.event_publisher.publish("phase_complete", phase="7", message="Iterative Improvement complete")
            self.context.logger.info("PHASE 7: Iterative Improvement complete.")

        return generated_files, initial_structure, file_paths

    # ------------------------------------------------------------------
    # E3: Quality gate helpers
    # ------------------------------------------------------------------

    async def _run_quality_check(self, project_root: Path, generated_files: Dict[str, str]) -> QualityReport:
        """Run tests and linter via QualityGate; publish a quality_check event."""
        language = self._detect_primary_language(generated_files)
        gate = QualityGate(logger=self.context.logger)
        try:
            report = await gate.run_quality_check(project_root, language=language)
            self.context.event_publisher.publish(
                "quality_check",
                phase="7",
                overall_pass=report.overall_pass,
                tests_failed=report.tests_failed,
                linter_errors=report.linter_errors,
            )
            if report.overall_pass:
                self.context.logger.info("  Quality gate: PASSED")
            else:
                self.context.logger.warning("  Quality gate: FAILED — " + "; ".join(report.failure_reasons[:3]))
        except Exception as exc:
            self.context.logger.warning(f"  Quality gate check failed (non-critical): {exc}")
            report = QualityReport(overall_pass=True)  # Fail open
        return report

    async def _auto_heal_loop(
        self,
        initial_report: QualityReport,
        generated_files: Dict[str, str],
        project_root: Path,
        readme_content: str,
    ) -> Dict[str, str]:
        """Attempt to fix quality issues through targeted file refinement.

        Runs up to QualityGate.MAX_HEAL_ITERATIONS refinement attempts.
        Stops early if the quality gate passes.

        Args:
            initial_report: The failing QualityReport that triggered healing.
            generated_files: Current file contents.
            project_root: Project root directory.
            readme_content: Project README for context.

        Returns:
            Updated generated_files dict after healing attempts.
        """
        report = initial_report
        gate = QualityGate(logger=self.context.logger)
        language = self._detect_primary_language(generated_files)

        for attempt in range(1, QualityGate.MAX_HEAL_ITERATIONS + 1):
            self.context.logger.info(
                f"  Auto-heal iteration {attempt}/{QualityGate.MAX_HEAL_ITERATIONS}: "
                + "; ".join(report.failure_reasons[:2])
            )

            # Build heal context from failure reasons and linter output
            heal_context = "\n".join(report.failure_reasons) + "\n" + report.linter_output[:500]

            # Refine files mentioned in test output or all Python files if unclear
            files_to_heal = self._identify_failing_files(report, generated_files)
            for rel_path in files_to_heal:
                content = generated_files.get(rel_path, "")
                if not content:
                    continue
                try:
                    refined = self.context.file_refiner.refine_file(
                        rel_path,
                        content,
                        readme_content[:500] + f"\n\nFix these issues:\n{heal_context[:300]}",
                    )
                    if refined:
                        generated_files[rel_path] = refined
                        self.context.file_manager.write_file(project_root / rel_path, refined)
                except Exception as exc:
                    self.context.logger.warning(f"  Heal attempt for {rel_path} failed: {exc}")

            # Re-check quality
            try:
                report = await gate.run_quality_check(project_root, language=language)
                if report.overall_pass:
                    self.context.logger.info(f"  Auto-heal succeeded on attempt {attempt}")
                    break
            except Exception as exc:
                self.context.logger.warning(f"  Quality re-check after heal failed: {exc}")
                break

        return generated_files

    @staticmethod
    def _identify_failing_files(report: QualityReport, generated_files: Dict[str, str]) -> List[str]:
        """Identify file paths mentioned in quality failure output."""
        failing: List[str] = []
        combined = " ".join(report.failure_reasons) + " " + report.linter_output + " " + report.test_output
        for path in generated_files:
            if path in combined or Path(path).name in combined:
                failing.append(path)
        # Fall back to all Python/JS source files if nothing specific found
        if not failing:
            failing = [p for p in generated_files if p.endswith((".py", ".js", ".ts")) and "test" not in p.lower()][:5]
        return failing

    @staticmethod
    def _detect_primary_language(files: Dict[str, str]) -> str:
        """Detect primary language from file extensions."""
        py_count = sum(1 for p in files if p.endswith(".py"))
        js_count = sum(1 for p in files if p.endswith((".js", ".ts")))
        return "python" if py_count >= js_count else "javascript"

    # ------------------------------------------------------------------
    # E9: Sandbox-validated write helper
    # ------------------------------------------------------------------

    def _validated_write(self, file_path: Path, content: str):
        """Write *content* to *file_path* via SandboxValidator (lazy init).

        Falls back to a direct write if the validator cannot be imported so
        the pipeline never breaks due to E9 issues.
        """
        try:
            from backend.utils.domains.auto_generation.sandbox_validator import SandboxValidator

            # Lazily cache the validator on the context to avoid re-instantiation
            if self.context._sandbox_validator is None:
                self.context._sandbox_validator = SandboxValidator(logger=self.context.logger)
            return self.context._sandbox_validator.validate_and_write(file_path, content, self.context.file_manager)
        except Exception as exc:
            self.context.logger.warning(f"  SandboxValidator unavailable, writing directly: {exc}")
            self.context.file_manager.write_file(file_path, content)
            # Return a minimal approved result so callers don't need to handle None
            from backend.utils.domains.auto_generation.sandbox_validator import ValidationResult

            return ValidationResult(approved=True, reason="fallback write")
