from typing import Dict, Any, List, Tuple
from pathlib import Path

from backend.interfaces.iagent_phase import IAgentPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


class DependencyReconciliationPhase(IAgentPhase):
    """
    Phase 5.6: Reconciles dependency files (e.g., requirements.txt, package.json)
    with actual imports found in the generated code.
    """
    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(self,
                      project_description: str,
                      project_name: str,
                      project_root: Path,
                      readme_content: str,
                      initial_structure: Dict[str, Any],
                      generated_files: Dict[str, str], # Files whose dependencies need reconciling
                      **kwargs: Any) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        
        file_paths = kwargs.get("file_paths", []) # Get from kwargs or assume context has it
        python_version = kwargs.get("python_version", "3.12")

        self.context.logger.info("PHASE 5.6: Reconciling dependency files with actual imports...")
        self.context.event_publisher.publish("phase_start", phase="5.6", message="Starting dependency reconciliation")
        
        # Call the _reconcile_requirements method from the AutoAgent instance via context
        # This is a temporary dependency to AutoAgent, will be refactored later
        generated_files = self.context.auto_agent._reconcile_requirements(generated_files, project_root, python_version)
        
        self.context.event_publisher.publish("phase_complete", phase="5.6", message="Dependency reconciliation complete")
        self.context.logger.info("PHASE 5.6 complete.")

        return generated_files, initial_structure, file_paths
