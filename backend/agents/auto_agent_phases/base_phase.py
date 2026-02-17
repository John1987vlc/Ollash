"""Base phase class with shared boilerplate for all AutoAgent phases.

Encapsulates common patterns: event publishing, logging, error handling,
and file_paths extraction from kwargs.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase
from backend.utils.core.exceptions import PipelinePhaseError


class BasePhase(IAgentPhase):
    """Base class for all pipeline phases with shared boilerplate.

    Subclasses should override `run()` instead of `execute()`.
    The `execute()` method handles event publishing, logging, and error handling.
    """

    phase_id: str = ""
    phase_label: str = ""
    category: str = "generation"

    def __init__(self, context: PhaseContext):
        self.context = context

    @property
    def phase_name(self) -> str:
        return self.phase_id or self.__class__.__name__

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
        file_paths: List[str] = kwargs.pop("file_paths", [])

        self._publish_start()
        self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE {self.phase_name}: {self.phase_label}...")

        try:
            result = await self.run(
                project_description=project_description,
                project_name=project_name,
                project_root=project_root,
                readme_content=readme_content,
                initial_structure=initial_structure,
                generated_files=generated_files,
                file_paths=file_paths,
                **kwargs,
            )
            self._publish_complete()
            self.context.logger.info(f"[PROJECT_NAME:{project_name}] PHASE {self.phase_name} complete.")
            return result
        except PipelinePhaseError:
            raise
        except Exception as e:
            self._publish_error(str(e))
            raise PipelinePhaseError(self.phase_name, str(e)) from e

    async def run(
        self,
        project_description: str,
        project_name: str,
        project_root: Path,
        readme_content: str,
        initial_structure: Dict[str, Any],
        generated_files: Dict[str, str],
        file_paths: List[str],
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        """Override this method in subclasses. file_paths is already extracted."""
        raise NotImplementedError(f"{self.__class__.__name__} must implement run()")

    def _publish_start(self, message: Optional[str] = None) -> None:
        self.context.event_publisher.publish(
            "phase_start",
            phase=self.phase_name,
            message=message or f"Starting {self.phase_label or self.phase_name}",
        )

    def _publish_complete(self, message: Optional[str] = None) -> None:
        self.context.event_publisher.publish(
            "phase_complete",
            phase=self.phase_name,
            message=message or f"{self.phase_label or self.phase_name} complete",
            status="success",
        )

    def _publish_error(self, error: str) -> None:
        self.context.event_publisher.publish(
            "phase_complete",
            phase=self.phase_name,
            message=f"{self.phase_label or self.phase_name} failed: {error}",
            status="error",
        )

    def _write_file(self, project_root: Path, rel_path: str, content: str, generated_files: Dict[str, str],
                     file_paths: List[str]) -> None:
        """Helper to write a file and update tracking structures."""
        generated_files[rel_path] = content
        self.context.file_manager.write_file(project_root / rel_path, content)
        if rel_path not in file_paths:
            file_paths.append(rel_path)
