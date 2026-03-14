import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

from backend.agents.auto_agent_phases.phase_context import PhaseContext
from backend.interfaces.iagent_phase import IAgentPhase
from backend.utils.core.io.git_manager import GitManager


class FinalReviewPhase(IAgentPhase):
    """
    Phase 6: Performs a final review of the generated project.

    Extended with an interactive Git decision gate:
    - Initializes a Git repository in the generated project.
    - Optionally pushes to a remote GitHub/GitLab repository.
    - The user provides ``git_push=True``, ``repo_name``, and ``git_token``
      via CLI kwargs or the Web UI to trigger the remote push.
    """

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

        self.context.logger.info("PHASE 6: Final review...")
        self.context.event_publisher.publish_sync("phase_start", phase="6", message="Starting final review")

        # --- Standard review ---
        validation_summary = self.context.file_completeness_checker.get_validation_summary(generated_files)
        try:
            review = self.context.project_reviewer.review(
                project_name, readme_content[:500], file_paths, validation_summary
            )
            review_file_path = "PROJECT_REVIEW.md"
            generated_files[review_file_path] = review
            self.context.file_manager.write_file(project_root / review_file_path, review)
            self.context.event_publisher.publish_sync(
                "phase_complete",
                phase="6",
                message="Final review complete",
                data={"review_summary": review[:200]},
            )
        except Exception as e:
            self.context.logger.error(f"  Error during review: {e}")
            self.context.event_publisher.publish_sync(
                "phase_complete",
                phase="6",
                message="Final review failed",
                status="error",
                error=str(e),
            )

        # --- Interactive Git decision gate ---
        git_push_requested = kwargs.get("git_push", False)
        repo_name = kwargs.get("repo_name", "")
        git_token = kwargs.get("git_token", "")

        git_repo_url = kwargs.get("git_repo_url", "")
        git_branch = kwargs.get("git_branch", "main")
        push_target = git_repo_url or repo_name

        if git_push_requested and (git_repo_url or repo_name):
            self.context.logger.info(f"Git decision gate: initializing repo for '{push_target}'")
            self.context.event_publisher.publish_sync(
                "phase_start",
                phase="6-git",
                message=f"Initializing Git and pushing to {push_target}",
            )

            try:
                git = GitManager(repo_path=str(project_root))
                self._initialize_git_repo(git, project_name)

                if git_token:
                    push_result = self._push_to_remote(
                        git,
                        repo_name,
                        git_token,
                        organization=kwargs.get("git_organization"),
                        git_repo_url=git_repo_url,
                        git_branch=git_branch,
                    )
                    self.context.logger.info(f"Git push result: {push_result}")
                    self.context.event_publisher.publish_sync(
                        "phase_complete",
                        phase="6-git",
                        message=f"Project pushed to {push_target}",
                        data=push_result,
                    )
                else:
                    self.context.logger.info("Git initialized locally (no token for remote push)")
                    self.context.event_publisher.publish_sync(
                        "phase_complete",
                        phase="6-git",
                        message="Git initialized locally",
                    )
            except Exception as e:
                self.context.logger.error(f"Git operation failed: {e}")
                self.context.event_publisher.publish_sync(
                    "phase_complete",
                    phase="6-git",
                    message="Git operation failed",
                    status="error",
                    error=str(e),
                )

        return generated_files, initial_structure, file_paths

    # ------------------------------------------------------------------
    # Git helpers
    # ------------------------------------------------------------------

    def _initialize_git_repo(self, git: GitManager, project_name: str) -> None:
        """Initialize a Git repository and create the first commit."""
        git_dir = Path(git.repo_path) / ".git"
        if not git_dir.exists():
            git._run_git("init")
            self.context.logger.info("Git repository initialized")

        git.add()
        git.commit(f"Initial commit - {project_name} generated by Ollash AutoAgent")
        self.context.logger.info("Initial commit created")

    def _push_to_remote(
        self,
        git: GitManager,
        repo_name: str,
        token: str,
        organization: Optional[str] = None,
        git_repo_url: str = "",
        git_branch: str = "main",
    ) -> Dict[str, Any]:
        """Push to remote.

        When *git_repo_url* is provided the caller already has a pre-created
        empty repository (the typical wizard flow).  In that case we skip
        ``gh repo create`` and push directly to the supplied URL.

        When no URL is given we fall back to the original behaviour: try
        ``gh repo create`` first, then a manual ``git push`` as a safety net.
        """
        if git_repo_url:
            return self._push_to_existing_repo(git, git_repo_url, token, git_branch)

        # --- Create-and-push path (no pre-created repo) ---
        visibility = "--private"
        org_flag = f"--org {organization}" if organization else ""
        env = {**os.environ, "GH_TOKEN": token}

        try:
            result = subprocess.run(
                f"gh repo create {repo_name} {visibility} {org_flag} --source=. --push",
                shell=True,
                capture_output=True,
                text=True,
                cwd=git.repo_path,
                env=env,
                timeout=60,
            )
            if result.returncode == 0:
                return {
                    "success": True,
                    "method": "gh_cli",
                    "output": result.stdout.strip(),
                }
        except Exception:
            pass

        # Fallback: manual remote + push
        ns = organization or "user"
        remote_url = f"https://{token}@github.com/{ns}/{repo_name}.git"
        git._run_git("remote", "add", "origin", remote_url)
        push_result = git._run_git("push", "-u", "origin", git_branch)

        if not push_result.get("success") and git_branch != "master":
            push_result = git._run_git("push", "-u", "origin", "master")

        return {
            "success": push_result.get("success", False),
            "method": "git_push",
            "output": push_result.get("output", ""),
            "error": push_result.get("error", ""),
        }

    def _push_to_existing_repo(
        self,
        git: GitManager,
        git_repo_url: str,
        token: str,
        git_branch: str = "main",
    ) -> Dict[str, Any]:
        """Push to a pre-created empty repository at *git_repo_url*.

        The token is inserted into the HTTPS URL so ``git push`` can
        authenticate without an interactive prompt.
        """
        parsed = urlparse(git_repo_url)
        # Build authenticated URL: https://token@github.com/org/repo.git
        authenticated_url = urlunparse(parsed._replace(netloc=f"{token}@{parsed.netloc}"))

        git._run_git("remote", "add", "origin", authenticated_url)
        push_result = git._run_git("push", "-u", "origin", git_branch)

        if not push_result.get("success") and git_branch != "master":
            push_result = git._run_git("push", "-u", "origin", "master")

        return {
            "success": push_result.get("success", False),
            "method": "direct_push",
            "output": push_result.get("output", ""),
            "error": push_result.get("error", ""),
        }
