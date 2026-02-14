from typing import Dict, Any, List, Tuple
from pathlib import Path

from backend.interfaces.iagent_phase import IAgentPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


class LicenseCompliancePhase(IAgentPhase):
    """
    Phase 5.56: Checks license compliance for generated files.
    """
    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(self,
                      project_description: str,
                      project_name: str,
                      project_root: Path,
                      readme_content: str,
                      initial_structure: Dict[str, Any],
                      generated_files: Dict[str, str], # Files to be checked
                      **kwargs: Any) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        
        file_paths = kwargs.get("file_paths", []) # Get from kwargs or assume context has it

        self.context.logger.info("PHASE 5.56: License Compliance Check...")
        self.context.event_publisher.publish("phase_start", phase="5.56", message="Starting license compliance check")
        
        for rel_path, content in generated_files.items():
            if not self.context.policy_enforcer.is_license_compliant(project_root / rel_path):
                self.context.logger.warning(f"  File {rel_path} has a non-compliant license.")
        
        self.context.event_publisher.publish("phase_complete", phase="5.56", message="License compliance check complete")
        self.context.logger.info("PHASE 5.56 complete.")

        return generated_files, initial_structure, file_paths
