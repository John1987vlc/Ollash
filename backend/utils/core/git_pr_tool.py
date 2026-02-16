"""
Git PR Tool — Automated Pull Request and Branch Management

Wraps GitManager + ``gh`` CLI to provide the agent with branch creation,
commit, push, and PR management capabilities. Used by the Autonomous
Maintenance system and available as a standalone tool.
"""

import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.git_manager import GitManager


@dataclass
class PRResult:
    """Result of a PR creation attempt."""

    success: bool
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "pr_url": self.pr_url,
            "pr_number": self.pr_number,
            "error": self.error,
        }


class GitPRTool:
    """High-level Git operations for automated PR workflows."""

    def __init__(self, repo_path: str, logger: AgentLogger):
        self.git = GitManager(repo_path=repo_path)
        self.logger = logger

    # ------------------------------------------------------------------
    # Branch management
    # ------------------------------------------------------------------

    def create_feature_branch(self, branch_name: str) -> Dict[str, Any]:
        """Create and switch to a new feature branch."""
        result = self.git.checkout(branch_name, create=True)
        if result.get("success"):
            self.logger.info(f"Created branch: {branch_name}")
        else:
            self.logger.error(f"Branch creation failed: {result.get('error')}")
        return result

    def switch_branch(self, branch_name: str) -> Dict[str, Any]:
        """Switch to an existing branch."""
        return self.git.checkout(branch_name)

    def get_current_branch(self) -> str:
        """Return the name of the current branch."""
        return self.git.current_branch()

    def list_branches(self) -> List[str]:
        """List all local branches."""
        return self.git.branches()

    # ------------------------------------------------------------------
    # Commit and push
    # ------------------------------------------------------------------

    def commit_all(self, message: str) -> Dict[str, Any]:
        """Stage all changes and commit."""
        return self.git.create_commit_with_all(message)

    def push(self, branch: Optional[str] = None) -> Dict[str, Any]:
        """Push the current branch to origin."""
        return self.git.push("origin", branch)

    # ------------------------------------------------------------------
    # Pull Request
    # ------------------------------------------------------------------

    def create_pr(
        self,
        title: str,
        body: str,
        base: str = "main",
        labels: Optional[List[str]] = None,
        draft: bool = False,
    ) -> PRResult:
        """Create a GitHub Pull Request via ``gh pr create``."""
        cmd = ["gh", "pr", "create", "--title", title, "--body", body, "--base", base]

        if labels:
            for label in labels:
                cmd.extend(["--label", label])
        if draft:
            cmd.append("--draft")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.git.repo_path,
                timeout=30,
            )

            if result.returncode == 0:
                pr_url = result.stdout.strip()
                pr_number = None
                if "/" in pr_url:
                    try:
                        pr_number = int(pr_url.rstrip("/").split("/")[-1])
                    except ValueError:
                        pass
                self.logger.info(f"PR created: {pr_url}")
                return PRResult(success=True, pr_url=pr_url, pr_number=pr_number)
            else:
                error = result.stderr.strip()
                self.logger.error(f"PR creation failed: {error}")
                return PRResult(success=False, error=error)

        except FileNotFoundError:
            return PRResult(success=False, error="gh CLI not installed. Install: https://cli.github.com")
        except subprocess.TimeoutExpired:
            return PRResult(success=False, error="PR creation timed out")
        except Exception as e:
            return PRResult(success=False, error=str(e))

    def list_open_prs(self) -> List[Dict[str, Any]]:
        """List open PRs in the repository."""
        try:
            result = subprocess.run(
                ["gh", "pr", "list", "--json", "number,title,url,state,headRefName"],
                capture_output=True,
                text=True,
                cwd=self.git.repo_path,
                timeout=15,
            )
            if result.returncode == 0:
                import json

                return json.loads(result.stdout)
        except Exception as e:
            self.logger.warning(f"Could not list PRs: {e}")

        return []

    def merge_pr(self, pr_number: int, method: str = "squash") -> Dict[str, Any]:
        """Merge a PR by number."""
        try:
            result = subprocess.run(
                ["gh", "pr", "merge", str(pr_number), f"--{method}", "--delete-branch"],
                capture_output=True,
                text=True,
                cwd=self.git.repo_path,
                timeout=30,
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout.strip(),
                "error": result.stderr.strip(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Full workflow
    # ------------------------------------------------------------------

    def full_improvement_workflow(
        self,
        branch_name: str,
        commit_message: str,
        pr_title: str,
        pr_body: str,
        base_branch: str = "main",
    ) -> PRResult:
        """
        Complete workflow: create branch -> commit -> push -> create PR.

        Returns the PR result.
        """
        # Create branch
        br = self.create_feature_branch(branch_name)
        if not br.get("success"):
            return PRResult(success=False, error=f"Branch creation failed: {br.get('error')}")

        # Commit
        cm = self.commit_all(commit_message)
        if not cm.get("success"):
            self.switch_branch(base_branch)
            return PRResult(success=False, error=f"Commit failed: {cm.get('error')}")

        # Push
        ps = self.push(branch_name)
        if not ps.get("success"):
            self.switch_branch(base_branch)
            return PRResult(success=False, error=f"Push failed: {ps.get('error')}")

        # Create PR
        pr_result = self.create_pr(pr_title, pr_body, base=base_branch)

        # Switch back to base
        self.switch_branch(base_branch)

        return pr_result
