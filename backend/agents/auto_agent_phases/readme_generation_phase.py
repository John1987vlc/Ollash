from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase


class ReadmeGenerationPhase(IAgentPhase):
    """
    Phase 1: Generates the initial README.md for the project.
    """

    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(
        self,
        project_description: str,
        project_name: str,
        project_root: Path,
        readme_content: str,  # Initial empty or existing README
        initial_structure: Dict[str, Any],
        generated_files: Dict[str, str],
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 1: Generating README.md...")
        self.context.event_publisher.publish("phase_start", phase="1", message="Generating README.md")

        _template_name = kwargs.get("template_name", "default")
        _python_version = kwargs.get("python_version", "3.12")
        _license_type = kwargs.get("license_type", "MIT")
        _include_docker = kwargs.get("include_docker", False)

        # Generate README with richer context
        readme = self.context.project_planner.generate_readme(
            project_name=project_name, project_description=project_description, project_structure=str(initial_structure)
        )

        readme_file_path = "README.md"
        generated_files[readme_file_path] = readme
        full_readme_path = project_root / readme_file_path
        self.context.file_manager.write_file(full_readme_path, readme)  # Use file_manager

        # Detect project type from description + generated README (zero LLM calls)
        try:
            from backend.utils.domains.auto_generation.project_type_detector import ProjectTypeDetector

            _type_info = ProjectTypeDetector.detect(project_description, readme)
            self.context.project_type_info = _type_info
            if _type_info.project_type != "unknown":
                self.context.logger.info(
                    f"[ProjectTypeDetector] Detected: {_type_info.project_type} "
                    f"(confidence={_type_info.confidence:.2f}), "
                    f"allowed={sorted(_type_info.allowed_extensions)}"
                )
                self.context.decision_blackboard.record_decision(
                    key="project_type",
                    value=_type_info.project_type,
                    context=f"Keywords: {', '.join(_type_info.detected_keywords[:5])}",
                )
                self.context.decision_blackboard.record_decision(
                    key="allowed_extensions",
                    value=",".join(sorted(_type_info.allowed_extensions)),
                    context="File extension whitelist for this project type",
                )
            else:
                self.context.logger.info(
                    "[ProjectTypeDetector] Unknown project type — all extensions allowed."
                )
        except Exception as _det_exc:
            self.context.logger.debug(
                f"[ProjectTypeDetector] Detection failed (non-fatal): {_det_exc}"
            )

        # F36: Index README for RAG support
        try:
            self.context.documentation_manager.index_documentation(full_readme_path)
        except Exception as e:
            self.context.logger.warning(f"Failed to index README for RAG: {e}")

        self.context.event_publisher.publish("phase_complete", phase="1", message="README generated")
        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE 1 complete.")

        return (
            generated_files,
            initial_structure,
            [readme_file_path],
        )  # Return readme_file_path as first generated file path
