from typing import Dict, Any, List, Tuple
from pathlib import Path

from backend.interfaces.iagent_phase import IAgentPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


class FinalReviewPhase(IAgentPhase):
    """
    Phase 6: Performs a final review of the generated project.
    """
    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(self,
                      project_description: str,
                      project_name: str,
                      project_root: Path,
                      readme_content: str,
                      initial_structure: Dict[str, Any],
                      generated_files: Dict[str, str], # Files to be reviewed
                      **kwargs: Any) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:

        file_paths = kwargs.get("file_paths", []) # Get from kwargs or assume context has it

        self.context.logger.info("PHASE 6: Final review...")
        self.context.event_publisher.publish("phase_start", phase="6", message="Starting final review")

        validation_summary = self.context.file_completeness_checker.get_validation_summary(generated_files)
        try:
            review = self.context.project_reviewer.review(project_name, readme_content[:500], file_paths, validation_summary)
            review_file_path = "PROJECT_REVIEW.md"
            generated_files[review_file_path] = review
            self.context.file_manager.write_file(project_root / review_file_path, review)
            self.context.event_publisher.publish("phase_complete", phase="6", message="Final review complete", data={"review_summary": review[:200]})
        except Exception as e:
            self.context.logger.error(f"  Error during review: {e}")
            self.context.event_publisher.publish("phase_complete", phase="6", message="Final review failed", status="error", error=str(e))

        return generated_files, initial_structure, file_paths
