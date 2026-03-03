from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase


class DependencyReconciliationPhase(IAgentPhase):
    """
    Phase 5.6: Reconciles dependency files (e.g., requirements.txt, package.json)
    with actual imports found in the generated code.
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
        generated_files: Dict[str, str],  # Files whose dependencies need reconciling
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        file_paths = kwargs.get("file_paths", [])  # Get from kwargs or assume context has it

        self.context.logger.info("PHASE 5.6: Reconciling dependency files with actual imports...")
        await self.context.event_publisher.publish(
            "phase_start", phase="5.6", message="Starting dependency reconciliation"
        )

        # Opt 5: Capture pre-reconciliation imports to detect mismatches for ErrorKnowledgeBase
        imports_before: Dict[str, Any] = {}
        if self.context._is_small_model() or self.context._opt_enabled("opt5_anti_pattern_injection"):
            try:
                imports_before = self.context.dependency_scanner.scan_all_imports(generated_files)
            except Exception:
                imports_before = {}

        # Use the specialized DependencyScanner directly from context
        # This replaces the circular dependency on AutoAgent
        generated_files = self.context.dependency_scanner.reconcile_dependencies(generated_files, project_root)

        # Opt 5: Record any newly-added packages as anti-patterns in ErrorKnowledgeBase
        if (
            self.context._is_small_model() or self.context._opt_enabled("opt5_anti_pattern_injection")
        ) and imports_before:
            try:
                imports_after = self.context.dependency_scanner.scan_all_imports(generated_files)
                for lang, pkgs_after in imports_after.items():
                    pkgs_before = imports_before.get(lang, set())
                    new_pkgs = set(pkgs_after) - set(pkgs_before)
                    if new_pkgs:
                        self.context.error_knowledge_base.record_error(
                            file_path=f"requirements/{lang}",
                            error_type="dependency_mismatch",
                            error_message=(
                                f"Missing {lang} packages detected during reconciliation: {', '.join(sorted(new_pkgs))}"
                            ),
                            file_content="",
                            context=f"Auto-detected by DependencyReconciliationPhase for project: {project_name}",
                            solution=(
                                f"Ensure {', '.join(sorted(new_pkgs))} are declared in the dependency file for {lang}"
                            ),
                        )
                        self.context.logger.info(f"[Opt5] Recorded dependency mismatch pattern for {lang}: {new_pkgs}")
            except Exception as e:
                self.context.logger.info(f"[Opt5] Could not record dependency patterns: {e}")

        await self.context.event_publisher.publish(
            "phase_complete", phase="5.6", message="Dependency reconciliation complete"
        )
        self.context.logger.info("PHASE 5.6 complete.")

        return generated_files, initial_structure, file_paths
