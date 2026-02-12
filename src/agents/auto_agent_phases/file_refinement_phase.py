from typing import Dict, Any, List, Tuple
from pathlib import Path

from src.interfaces.iagent_phase import IAgentPhase
from src.agents.auto_agent_phases.phase_context import PhaseContext


class FileRefinementPhase(IAgentPhase):
    """
    Phase 5: Refines the content of generated files.
    """
    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(self,
                      project_description: str,
                      project_name: str,
                      project_root: Path,
                      readme_content: str,
                      initial_structure: Dict[str, Any],
                      generated_files: Dict[str, str], # This will be refined
                      **kwargs: Any) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        
        file_paths = kwargs.get("file_paths", []) # Get from kwargs or assume context has it

        self.context.logger.info("PHASE 5: Refining files...")
        self.context.event_publisher.publish("phase_start", phase="5", message="Refining files")
        
        for idx, (rel_path, content) in enumerate(list(generated_files.items()), 1):
            if not content or len(content) < 10:
                continue
            self.context.event_publisher.publish("tool_start", tool_name="file_refinement", file=rel_path, progress=f"{idx}/{len(file_paths)}")
            self.context.logger.info(f"  [{idx}/{len(file_paths)}] Refining {rel_path}")
            try:
                refined = self.context.file_refiner.refine_file(rel_path, content, readme_content[:1000])
                if refined:
                    generated_files[rel_path] = refined
                    self.context.file_manager.write_file(project_root / rel_path, refined)
                    self.context.event_publisher.publish("tool_output", tool_name="file_refinement", file=rel_path, status="success")
                else:
                    self.context.event_publisher.publish("tool_output", tool_name="file_refinement", file=rel_path, status="skipped", message="Refinement not significant")
            except Exception as e:
                self.context.logger.error(f"  Error refining {rel_path}: {e}")
                self.context.event_publisher.publish("tool_output", tool_name="file_refinement", file=rel_path, status="error", message=str(e))
            self.context.event_publisher.publish("tool_end", tool_name="file_refinement", file=rel_path)
        
        self.context.event_publisher.publish("phase_complete", phase="5", message="Files refined")
        self.context.logger.info("PHASE 5 complete.")

        return generated_files, initial_structure, file_paths
