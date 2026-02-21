"""
CI/CD Healing Phase

Monitors GitHub Actions after git push and automatically fixes CI failures
using the CICDHealer service. Runs after FinalReviewPhase.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase
from backend.utils.core.io.git_manager import GitManager


class CICDHealingPhase(IAgentPhase):
    """
    Post-CI auto-correction phase.

    After FinalReviewPhase pushes to GitHub, this phase:
    1. Polls GitHub Actions for workflow completion
    2. If CI fails, fetches logs and analyzes with CICDHealer
    3. Generates fix patches via LLM
    4. Commits and pushes fixes
    5. Re-checks CI (max 3 healing attempts)
    """

    MAX_HEALING_ATTEMPTS = 3
    POLL_INTERVAL_SECONDS = 30
    MAX_POLL_DURATION_SECONDS = 600  # 10 minutes

    def __init__(self, context: PhaseContext):
        self.context = context

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
        file_paths = kwargs.get("file_paths", [])

        git_push_requested = kwargs.get("git_push", False)
        if not git_push_requested:
            self.context.logger.info("CICD Healing: Skipped (git_push not enabled)")
            return generated_files, initial_structure, file_paths

        if not self.context.cicd_healer:
            self.context.logger.warning("CICD Healing: Skipped (CICDHealer not available)")
            return generated_files, initial_structure, file_paths

        self.context.logger.info("PHASE CI/CD: Starting CI/CD healing monitor...")
        self.context.event_publisher.publish("phase_start", phase="cicd_healing", message="Monitoring CI/CD pipeline")

        healing_attempt = 0
        ci_passed = False

        while not ci_passed and healing_attempt < self.MAX_HEALING_ATTEMPTS:
            # Wait for workflow to complete
            run_result = await self._wait_for_workflow_completion(project_root)

            if run_result is None:
                self.context.logger.warning("CICD Healing: Could not detect workflow run")
                break

            if run_result.get("conclusion") == "success":
                ci_passed = True
                self.context.logger.info("CICD Healing: CI passed successfully!")
                self.context.event_publisher.publish(
                    "tool_output",
                    tool_name="cicd_healing",
                    status="passed",
                    message="CI/CD pipeline passed",
                )
                break

            # CI failed - attempt healing
            healing_attempt += 1
            self.context.logger.info(f"CICD Healing: Attempt {healing_attempt}/{self.MAX_HEALING_ATTEMPTS}")
            self.context.event_publisher.publish(
                "tool_start",
                tool_name="cicd_healing",
                attempt=healing_attempt,
                message=f"CI failed, healing attempt {healing_attempt}",
            )

            # Fetch and analyze logs
            run_id = run_result.get("databaseId", "")
            workflow_log = self._fetch_workflow_logs(project_root, run_id)

            if not workflow_log:
                self.context.logger.warning("CICD Healing: Could not fetch workflow logs")
                break

            analysis = self.context.cicd_healer.analyze_failure(
                workflow_log, workflow_name=run_result.get("name", "CI")
            )

            self.context.event_publisher.publish(
                "tool_output",
                tool_name="cicd_healing_analysis",
                category=analysis.category,
                root_cause=analysis.root_cause,
                fixes=analysis.suggested_fixes,
            )

            # Generate and apply fixes
            fixes = await self.context.cicd_healer.generate_fix(analysis, generated_files)

            if not fixes:
                self.context.logger.warning("CICD Healing: No fixes generated")
                break

            # Apply fixes
            for file_path, new_content in fixes.items():
                if file_path in generated_files:
                    generated_files[file_path] = new_content
                    self.context.file_manager.write_file(project_root / file_path, new_content)
                    self.context.logger.info(f"  Fixed: {file_path}")

            # Commit and push
            self._commit_and_push_fix(project_root, healing_attempt, analysis.root_cause)

            self.context.event_publisher.publish(
                "tool_end",
                tool_name="cicd_healing",
                attempt=healing_attempt,
                fixes_applied=len(fixes),
            )

        # Final status
        if ci_passed:
            self.context.event_publisher.publish(
                "phase_complete",
                phase="cicd_healing",
                message="CI/CD pipeline passed",
                status="success",
            )
        else:
            self.context.logger.warning(f"CICD Healing: CI still failing after {healing_attempt} attempts")
            self.context.event_publisher.publish(
                "phase_complete",
                phase="cicd_healing",
                message=f"CI healing exhausted ({healing_attempt} attempts)",
                status="warning",
            )

        return generated_files, initial_structure, file_paths

    async def _wait_for_workflow_completion(self, project_root: Path) -> Dict[str, Any] | None:
        """Poll GitHub Actions for the latest workflow run status."""
        elapsed = 0

        while elapsed < self.MAX_POLL_DURATION_SECONDS:
            try:
                result = subprocess.run(
                    [
                        "gh",
                        "run",
                        "list",
                        "--limit",
                        "1",
                        "--json",
                        "databaseId,status,conclusion,name,headBranch",
                    ],
                    capture_output=True,
                    text=True,
                    cwd=str(project_root),
                    timeout=15,
                )

                if result.returncode == 0 and result.stdout.strip():
                    runs = json.loads(result.stdout)
                    if runs:
                        run = runs[0]
                        status = run.get("status", "")

                        if status == "completed":
                            return run

                        self.context.logger.info(f"  CI status: {status} (waiting...)")
            except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
                self.context.logger.debug(f"  Polling error: {e}")

            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
            elapsed += self.POLL_INTERVAL_SECONDS

        return None

    def _fetch_workflow_logs(self, project_root: Path, run_id: Any) -> str:
        """Fetch workflow logs from GitHub Actions."""
        try:
            result = subprocess.run(
                ["gh", "run", "view", str(run_id), "--log"],
                capture_output=True,
                text=True,
                cwd=str(project_root),
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout
        except Exception as e:
            self.context.logger.error(f"Failed to fetch CI logs: {e}")

        return ""

    def _commit_and_push_fix(self, project_root: Path, attempt: int, root_cause: str) -> None:
        """Commit the healing fixes and push to remote."""
        try:
            git = GitManager(repo_path=str(project_root))
            git.add()
            git.commit(f"fix(ci): Auto-heal attempt {attempt} - {root_cause}")
            git.push("origin")
            self.context.logger.info(f"  Pushed CI fix (attempt {attempt})")
        except Exception as e:
            self.context.logger.error(f"  Failed to push CI fix: {e}")
