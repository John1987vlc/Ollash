from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase


class IterativeImprovementPhase(IAgentPhase):
    """
    Phase 7: Conducts iterative improvement loops based on suggestions,
    planning, implementation, and re-verification.
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
                self.context.logger.info(f"PHASE 7: Iteration {loop_num + 1}/{num_refine_loops}")
                self.context.event_publisher.publish("iteration_start", phase="7", iteration=loop_num + 1)

                # 1. Suggest improvements
                self.context.event_publisher.publish(
                    "tool_start",
                    tool_name="suggest_improvements",
                    iteration=loop_num + 1,
                )
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
                            self.context.file_manager.write_file(project_root / rel_path, refined)
                            self.context.event_publisher.publish(
                                "tool_output",
                                tool_name="file_refinement",
                                file=rel_path,
                                status="success",
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
                generated_files = self.context.file_completeness_checker.verify_and_fix(
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
