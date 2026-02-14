from typing import Dict, Any, List, Tuple
from pathlib import Path

from backend.interfaces.iagent_phase import IAgentPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.utils.domains.auto_generation.structure_generator import StructureGenerator


class EmptyFileScaffoldingPhase(IAgentPhase):
    """
    Phase 3: Creates empty placeholder files and directories based on the generated structure.
    """
    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(self,
                      project_description: str,
                      project_name: str,
                      project_root: Path,
                      readme_content: str,
                      initial_structure: Dict[str, Any],
                      generated_files: Dict[str, str],
                      **kwargs: Any) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        
        file_paths = kwargs.get("file_paths", []) # Get from kwargs or assume context has it

        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 3: Creating empty placeholders...")
        self.context.event_publisher.publish("phase_start", phase="3", message="Creating empty files")
        
        StructureGenerator.create_empty_files(project_root, initial_structure)
        
        self.context.event_publisher.publish("phase_complete", phase="3", message="Empty files created")
        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 3 complete.")

        return generated_files, initial_structure, file_paths
