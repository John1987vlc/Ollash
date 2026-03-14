import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase
from backend.utils.domains.auto_generation.project_type_detector import ProjectTypeDetector
from backend.utils.domains.auto_generation.structure_generator import StructureGenerator  # For fallback structure


class StructureGenerationPhase(IAgentPhase):
    """
    Phase 2: Generates the project structure (folders and files) as a JSON object.
    """

    def __init__(self, context: PhaseContext):
        self.context = context

    def execute(
        self,
        project_description: str,
        project_name: str,
        project_root: Path,
        readme_content: str,
        initial_structure: Dict[str, Any],  # Will be updated here
        generated_files: Dict[str, str],
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 2: Generating project structure...")
        self.context.event_publisher.publish_sync("phase_start", phase="2", message="Generating project structure")

        template_name = kwargs.get("template_name", "default")
        python_version = kwargs.get("python_version", "3.12")
        license_type = kwargs.get("license_type", "MIT")
        include_docker = kwargs.get("include_docker", False)

        # Build extension constraint hint from detected project type (set by Phase 1)
        _type_info = getattr(self.context, "project_type_info", None)
        _allowed_exts: Optional[List[str]] = None
        _constraint_hint = ""
        if _type_info and _type_info.project_type != "unknown" and _type_info.confidence >= 0.10:
            _allowed_exts = sorted(_type_info.allowed_extensions)
            _forbidden_text = ProjectTypeDetector.get_forbidden_extensions_text(_type_info.allowed_extensions)
            _constraint_hint = (
                f"ONLY create files with these extensions: {', '.join(_allowed_exts)}. "
                + (f"DO NOT create files with: {_forbidden_text}. " if _forbidden_text else "")
                + f"This is a {_type_info.project_type.replace('_', ' ')} project."
            )
            self.context.logger.info(
                f"[Phase2] Applying extension constraint for '{_type_info.project_type}': {_allowed_exts}"
            )

        structure = self.context.structure_generator.generate(
            readme_content,
            max_retries=3,
            template_name=template_name,
            python_version=python_version,
            license_type=license_type,
            include_docker=include_docker,
            constraint_hint=_constraint_hint,
        )
        if not structure or (not structure.get("files") and not structure.get("folders")):
            self.context.logger.error(
                f"[PROJECT_NAME:{project_name}] Could not generate valid structure. Using fallback with template '{template_name}'."
            )
            structure = StructureGenerator.create_fallback_structure(
                readme_content,
                template_name=template_name,
                python_version=python_version,
                license_type=license_type,
                include_docker=include_docker,
                project_type=getattr(_type_info, "project_type", "") if _type_info else "",
            )

        # Post-generation filter: remove any files with disallowed extensions
        if _allowed_exts is not None:
            structure = StructureGenerator.filter_structure_by_extensions(
                structure, set(_allowed_exts), self.context.logger
            )
            self.context.logger.info("[Phase2] Structure filtered to allowed extensions.")

        structure_file_path = "project_structure.json"
        generated_files[structure_file_path] = json.dumps(structure, indent=2)
        self.context.file_manager.write_file(project_root / structure_file_path, generated_files[structure_file_path])

        file_paths = StructureGenerator.extract_file_paths(structure)

        self.context.event_publisher.publish_sync(
            "phase_complete",
            phase="2",
            message="Project structure generated",
            data={"files_planned": len(file_paths)},
        )
        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 2 complete: {len(file_paths)} files planned.")

        return generated_files, structure, file_paths
