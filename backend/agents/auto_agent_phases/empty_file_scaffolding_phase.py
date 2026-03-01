from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase
from backend.utils.domains.auto_generation.structure_generator import StructureGenerator


class EmptyFileScaffoldingPhase(IAgentPhase):
    """
    Phase 3: Creates empty placeholder files and directories based on the generated structure.
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
        file_paths = kwargs.get("file_paths", [])  # Get from kwargs or assume context has it

        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 3: Creating empty placeholders...")
        self.context.event_publisher.publish("phase_start", phase="3", message="Creating empty files")

        # Safety net: filter disallowed extensions before creating physical files
        _type_info = getattr(self.context, "project_type_info", None)
        if _type_info and _type_info.project_type != "unknown" and _type_info.confidence >= 0.10:
            initial_structure = StructureGenerator.filter_structure_by_extensions(
                initial_structure, set(_type_info.allowed_extensions), self.context.logger
            )
            self.context.logger.info("[Phase3] Pre-filtered structure to allowed extensions before scaffolding.")

        StructureGenerator.create_empty_files(project_root, initial_structure)

        self.context.event_publisher.publish("phase_complete", phase="3", message="Empty files created")
        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 3 complete.")

        return generated_files, initial_structure, file_paths
