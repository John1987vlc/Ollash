import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase


class StructurePreReviewPhase(IAgentPhase):
    """
    Phase 2.5: Performs a pre-review of the generated project structure.
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
        file_paths = kwargs.get(
            "file_paths", []
        )  # Get from kwargs or assume context has it

        self.context.logger.info(
            f"[PROJECT_NAME:{project_name}] PHASE 2.5: PreReview of structure..."
        )
        self.context.event_publisher.publish(
            "phase_start", phase="2.5", message="Starting structure pre-review"
        )

        structure_review = self.context.structure_pre_reviewer.review_structure(
            readme_content, initial_structure, project_name
        )

        review_file_path = "STRUCTURE_REVIEW.json"
        generated_files[review_file_path] = json.dumps(
            structure_review.to_dict(), indent=2
        )
        self.context.file_manager.write_file(
            project_root / review_file_path, generated_files[review_file_path]
        )

        if structure_review.status == "critical":
            self.context.logger.warning(
                f"[PROJECT_NAME:{project_name}] Structure has critical issues. Attempting fix..."
            )
            # Here, AutoAgent could potentially loop back or trigger a different phase to fix structure.
            # For now, we continue but log the warning.
        else:
            self.context.logger.info(
                f"[PROJECT_NAME:{project_name}] Structure review: {structure_review.status} (score: {structure_review.quality_score:.1f})"
            )

        self.context.event_publisher.publish(
            "phase_complete",
            phase="2.5",
            message="Structure pre-review complete",
            data={"quality_score": structure_review.quality_score},
        )
        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 2.5 complete.")

        return generated_files, initial_structure, file_paths
