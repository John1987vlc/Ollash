from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple
from pathlib import Path # NEW

class IAgentPhase(ABC):
    """
    Abstract Base Class defining the interface for a single phase within
    the AutoAgent's project generation pipeline.
    Each phase is responsible for a specific step in the project creation process.
    """

    @abstractmethod
    async def execute(self,
                      project_description: str,
                      project_name: str,
                      project_root: Path, # Assuming Path is imported elsewhere
                      readme_content: str,
                      initial_structure: Dict[str, Any],
                      generated_files: Dict[str, str], # Current state of generated files
                      **kwargs: Any) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        """
        Executes the logic for this specific phase of the AutoAgent pipeline.

        Args:
            project_description: The initial high-level description of the project.
            project_name: The name of the project.
            project_root: The root directory of the project being generated.
            readme_content: The content of the generated README.md.
            initial_structure: The JSON structure defined for the project.
            generated_files: A dictionary of {file_path: content} for files generated so far.
            **kwargs: Additional parameters specific to the phase or pipeline.

        Returns:
            A tuple containing:
            - Updated generated_files: A dictionary of {file_path: content} after this phase.
            - Updated initial_structure: The (potentially modified) JSON structure.
            - Updated file_paths: A list of file paths in the project.
        """
        pass
