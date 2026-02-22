from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase


class CodeQuarantinePhase(IAgentPhase):
    """
    Phase 5.55: Scans generated files for potentially unsafe code (e.g., 'subprocess', 'eval')
    and quarantines them.
    """

    def __init__(self, context: PhaseContext):
        self.context = context

    async def execute(
        self,
        project_description: str,
        project_name: str,
        project_root: Path,
        readme_content: str,
        initial_structure: Dict[str, Any],
        generated_files: Dict[str, str],  # Files to be scanned
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        file_paths = kwargs.get("file_paths", [])  # Get from kwargs or assume context has it

        self.context.logger.info("PHASE 5.55: Code Quarantine...")
        self.context.event_publisher.publish("phase_start", phase="5.55", message="Starting code quarantine")

        import re
        # Security patterns with word boundaries to avoid false positives like 'evaluation' or 'evaluateHand'
        unsafe_patterns = [
            re.compile(r"\beval\s*\("),
            re.compile(r"\bsubprocess\b"),
            re.compile(r"new\s+Function\s*\("),
            re.compile(r"\bexec\s*\("),
        ]

        for rel_path, content in generated_files.items():
            if not content:
                continue
            
            # Skip non-code files
            if rel_path.endswith('.json') or rel_path.endswith('.md') or rel_path.endswith('.txt'):
                continue

            is_unsafe = any(pattern.search(content) for pattern in unsafe_patterns)
            
            if is_unsafe:
                self.context.logger.warning(f"  Quarantining {rel_path} due to potentially unsafe content.")
                self.context.code_quarantine.quarantine_file(project_root / rel_path)

        self.context.event_publisher.publish("phase_complete", phase="5.55", message="Code quarantine complete")
        self.context.logger.info("PHASE 5.55 complete.")

        return generated_files, initial_structure, file_paths
