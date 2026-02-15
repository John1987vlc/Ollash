from typing import Dict, Any, List, Tuple
from pathlib import Path

from backend.interfaces.iagent_phase import IAgentPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


class VerificationPhase(IAgentPhase):
    """
    Phase 5.5: Performs a verification loop to validate and fix generated files.
    """
    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(self,
                      project_description: str,
                      project_name: str,
                      project_root: Path,
                      readme_content: str,
                      initial_structure: Dict[str, Any],
                      generated_files: Dict[str, str], # This will be verified and potentially fixed
                      **kwargs: Any) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:

        file_paths = kwargs.get("file_paths", []) # Get from kwargs or assume context has it

        self.context.logger.info("PHASE 5.5: Verification loop...")
        self.context.event_publisher.publish("phase_start", phase="5.5", message="Starting verification loop")

        generated_files = self.context.file_completeness_checker.verify_and_fix(generated_files, readme_content[:1000])

        for rel_path, content in generated_files.items():
            if content:
                self.context.file_manager.write_file(project_root / rel_path, content)

        self.context.event_publisher.publish("phase_complete", phase="5.5", message="Verification loop complete")
        self.context.logger.info("PHASE 5.5 complete.")

        return generated_files, initial_structure, file_paths
