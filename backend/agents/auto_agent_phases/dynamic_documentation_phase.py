"""
Dynamic Documentation Phase (E7) — Auto-update CHANGELOG, ROADMAP, and README.

Runs after each IterativeImprovementPhase cycle to keep project documentation in
sync with the code changes that the agent applied. No user intervention required.

Outputs:
- CHANGELOG.md  — prepended entry for the current auto-cycle
- ROADMAP.md    — regenerated from current improvement gaps and tech stack
- README.md     — "## Last Auto-Update" section updated with cycle summary
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase


class DynamicDocumentationPhase(IAgentPhase):
    """
    Phase 7.5 (inserted after IterativeImprovementPhase):
    Auto-generates and updates documentation files at the end of every auto-cycle.

    The phase is non-blocking: any LLM or I/O failures are logged as warnings and
    the pipeline continues. This ensures documentation issues never stop code delivery.
    """

    PHASE_NAME = "7.5"

    def __init__(self, context: PhaseContext):
        self.context = context

    def execute(
        self,
        project_description: str,
        project_name: str,
        project_root: Path,
        readme_content: str,
        initial_structure: Dict[str, Any],
        generated_files: Dict[str, str],
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        file_paths = kwargs.get("file_paths", [])

        self.context.logger.info(f"PHASE {self.PHASE_NAME}: Dynamic Documentation Update...")
        self.context.event_publisher.publish_sync(
            "phase_start",
            phase=self.PHASE_NAME,
            message="Auto-updating CHANGELOG, ROADMAP, and README",
        )

        cycle_changes = self._collect_cycle_changes()
        improvement_gaps = initial_structure.get("improvement_gaps", {})
        tech_stack_info = getattr(self.context, "tech_stack_info", None)

        # 1. Update CHANGELOG.md
        try:
            changelog_entry = self.context.project_planner.generate_changelog_entry(
                project_name=project_name,
                changes=cycle_changes,
            )
            existing_changelog = generated_files.get("CHANGELOG.md", "")
            new_changelog = self._prepend_entry(existing_changelog, changelog_entry)
            generated_files["CHANGELOG.md"] = new_changelog
            self.context.file_manager.write_file(project_root / "CHANGELOG.md", new_changelog)
            self.context.logger.info(f"  PHASE {self.PHASE_NAME}: CHANGELOG.md updated")
        except Exception as exc:
            self.context.logger.warning(f"  PHASE {self.PHASE_NAME}: CHANGELOG update failed (non-critical): {exc}")

        # 2. Update ROADMAP.md (only if there are improvement gaps)
        if improvement_gaps:
            try:
                roadmap_content = self.context.project_planner.generate_roadmap(
                    project_name=project_name,
                    improvement_gaps=improvement_gaps,
                    tech_stack_info=tech_stack_info,
                )
                generated_files["ROADMAP.md"] = roadmap_content
                self.context.file_manager.write_file(project_root / "ROADMAP.md", roadmap_content)
                self.context.logger.info(f"  PHASE {self.PHASE_NAME}: ROADMAP.md updated")
            except Exception as exc:
                self.context.logger.warning(f"  PHASE {self.PHASE_NAME}: ROADMAP update failed (non-critical): {exc}")

        # 3. Update README.md "## Last Auto-Update" section
        try:
            cycle_summary = self._build_cycle_summary(project_name, cycle_changes)
            existing_readme = generated_files.get("README.md", readme_content)
            updated_readme = self.context.project_planner.update_readme_summary(
                existing_readme=existing_readme,
                cycle_summary=cycle_summary,
            )
            generated_files["README.md"] = updated_readme
            self.context.file_manager.write_file(project_root / "README.md", updated_readme)
            self.context.logger.info(f"  PHASE {self.PHASE_NAME}: README.md Last Auto-Update section refreshed")
        except Exception as exc:
            self.context.logger.warning(f"  PHASE {self.PHASE_NAME}: README update failed (non-critical): {exc}")

        self.context.event_publisher.publish_sync(
            "phase_complete",
            phase=self.PHASE_NAME,
            message="Dynamic Documentation complete",
        )
        self.context.logger.info(f"PHASE {self.PHASE_NAME}: Dynamic Documentation complete.")
        return generated_files, initial_structure, file_paths

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _collect_cycle_changes(self) -> List[str]:
        """Extract human-readable change descriptions from context.logic_plan."""
        changes: List[str] = []
        logic_plan: Dict[str, Any] = getattr(self.context, "logic_plan", {}) or {}
        for file_path, plan_data in logic_plan.items():
            if isinstance(plan_data, dict):
                description = plan_data.get("description") or plan_data.get("purpose") or ""
                if description:
                    changes.append(f"{file_path}: {description}")
        if not changes:
            changes = ["Automated code improvements applied by Ollash Auto Mode"]
        return changes

    def _build_cycle_summary(self, project_name: str, changes: List[str]) -> str:
        """Build a compact text summary of the current auto-cycle."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        lines = [f"**{project_name}** — auto-cycle at {timestamp}", ""]
        lines += [f"- {c}" for c in changes[:10]]  # cap at 10 items
        return "\n".join(lines)

    @staticmethod
    def _prepend_entry(existing: str, new_entry: str) -> str:
        """Prepend *new_entry* before the first existing entry in a Keep-a-Changelog file."""
        if not existing.strip():
            header = "# Changelog\n\nAll notable changes to this project are documented here.\n\n"
            return header + new_entry + "\n"
        # Insert after the top-level header block (first blank line after any header)
        lines = existing.splitlines(keepends=True)
        insert_at = 0
        for i, line in enumerate(lines):
            if line.startswith("## "):
                insert_at = i
                break
            if line.strip() == "" and i > 0:
                insert_at = i + 1
        result = lines[:insert_at] + [new_entry + "\n"] + lines[insert_at:]
        return "".join(result)
