from typing import Dict, Any, List, Tuple
from pathlib import Path
import json

from backend.interfaces.iagent_phase import IAgentPhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.utils.domains.auto_generation.structure_generator import StructureGenerator # For fallback structure


class StructureGenerationPhase(IAgentPhase):
    """
    Phase 2: Generates the project structure (folders and files) as a JSON object.
    """
    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(self,
                      project_description: str,
                      project_name: str,
                      project_root: Path,
                      readme_content: str,
                      initial_structure: Dict[str, Any], # Will be updated here
                      generated_files: Dict[str, str],
                      **kwargs: Any) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:

        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 2: Generating project structure...")
        self.context.event_publisher.publish("phase_start", phase="2", message="Generating project structure")

        template_name = kwargs.get("template_name", "default")
        python_version = kwargs.get("python_version", "3.12")
        license_type = kwargs.get("license_type", "MIT")
        include_docker = kwargs.get("include_docker", False)

        structure = self.context.structure_generator.generate(
            readme_content, max_retries=3, template_name=template_name,
            python_version=python_version, license_type=license_type, include_docker=include_docker
        )
        if not structure or (not structure.get("files") and not structure.get("folders")):
            self.context.logger.error(f"[PROJECT_NAME:{project_name}] Could not generate valid structure. Using fallback with template '{template_name}'.")
            structure = StructureGenerator.create_fallback_structure(
                readme_content, template_name=template_name,
                python_version=python_version, license_type=license_type, include_docker=include_docker
            )

        structure_file_path = "project_structure.json"
        generated_files[structure_file_path] = json.dumps(structure, indent=2)
        self.context.file_manager.write_file(project_root / structure_file_path, generated_files[structure_file_path])

        file_paths = StructureGenerator.extract_file_paths(structure)

        self.context.event_publisher.publish("phase_complete", phase="2", message="Project structure generated", data={"files_planned": len(file_paths)})
        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 2 complete: {len(file_paths)} files planned.")

        return generated_files, structure, file_paths
