from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase


class ContentCompletenessPhase(IAgentPhase):
    """
    Phase 7.5: Checks the completeness of generated file content, detecting placeholders
    and attempting to complete them.
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
        generated_files: Dict[str, str],  # Files to be checked and completed
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        file_paths = kwargs.get(
            "file_paths", []
        )  # Get from kwargs or assume context has it

        self.context.logger.info(
            "PHASE 7.5: Checking content completeness (placeholder detection)..."
        )
        self.context.event_publisher.publish(
            "phase_start", phase="7.5", message="Checking content completeness"
        )

        incomplete_files = []
        for rel_path, content in generated_files.items():
            if not content:
                continue
            warning = self.context.file_validator.check_content_completeness(
                rel_path, content
            )
            if warning:
                self.context.logger.warning(f"  INCOMPLETE: {rel_path} — {warning}")
                incomplete_files.append(rel_path)

        if incomplete_files:
            self.context.logger.info(
                f"  Found {len(incomplete_files)} incomplete files, attempting to complete them..."
            )
            self.context.event_publisher.publish(
                "tool_start",
                tool_name="complete_incomplete_files",
                count=len(incomplete_files),
            )
            for rel_path in incomplete_files:
                content = generated_files[rel_path]
                try:
                    issues = [
                        {
                            "description": "File contains placeholder/stub content that needs real implementation",
                            "severity": "major",
                            "recommendation": "Replace all TODO, placeholder, and stub content with real implementations",
                        }
                    ]
                    refined = self.context.file_refiner.refine_file(
                        rel_path, content, readme_content[:2000], issues
                    )
                    if refined:
                        generated_files[rel_path] = refined
                        self.context.file_manager.write_file(
                            project_root / rel_path, refined
                        )
                        self.context.logger.info(f"    Completed: {rel_path}")
                        self.context.event_publisher.publish(
                            "tool_output",
                            tool_name="complete_incomplete_files",
                            file=rel_path,
                            status="success",
                        )
                except Exception as e:
                    self.context.logger.error(f"    Error completing {rel_path}: {e}")
                    self.context.event_publisher.publish(
                        "tool_output",
                        tool_name="complete_incomplete_files",
                        file=rel_path,
                        status="error",
                        message=str(e),
                    )

            # Re-verify after completing
            generated_files = self.context.file_completeness_checker.verify_and_fix(
                generated_files, readme_content[:2000]
            )
            for rel_path, content in generated_files.items():
                if content:
                    self.context.file_manager.write_file(
                        project_root / rel_path, content
                    )
            self.context.event_publisher.publish(
                "tool_end", tool_name="complete_incomplete_files"
            )

        self.context.event_publisher.publish(
            "phase_complete", phase="7.5", message="Content completeness check complete"
        )
        self.context.logger.info("PHASE 7.5 complete.")

        return generated_files, initial_structure, file_paths
