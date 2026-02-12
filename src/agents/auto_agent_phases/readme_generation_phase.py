from typing import Dict, Any, List, Tuple
from pathlib import Path

from src.interfaces.iagent_phase import IAgentPhase
from src.agents.auto_agent_phases.phase_context import PhaseContext
from src.utils.domains.auto_generation.structure_generator import StructureGenerator # For create_empty_files


class ReadmeGenerationPhase(IAgentPhase):
    """
    Phase 1: Generates the initial README.md for the project.
    """
    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(self,
                      project_description: str,
                      project_name: str,
                      project_root: Path,
                      readme_content: str, # Initial empty or existing README
                      initial_structure: Dict[str, Any],
                      generated_files: Dict[str, str],
                      **kwargs: Any) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        
        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 1: Generating README.md...")
        self.context.event_publisher.publish("phase_start", phase="1", message="Generating README.md")

        template_name = kwargs.get("template_name", "default")
        python_version = kwargs.get("python_version", "3.12")
        license_type = kwargs.get("license_type", "MIT")
        include_docker = kwargs.get("include_docker", False)

        # Generate README
        readme = self.context.project_planner.generate_readme(
            project_description, template_name, python_version, license_type, include_docker
        )
        
        readme_file_path = "README.md"
        generated_files[readme_file_path] = readme
        self.context.file_manager.write_file(project_root / readme_file_path, readme) # Use file_manager
        
        self.context.event_publisher.publish("phase_complete", phase="1", message="README generated")
        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 1 complete.")

        return generated_files, initial_structure, [readme_file_path] # Return readme_file_path as first generated file path
