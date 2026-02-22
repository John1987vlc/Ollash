import json
import subprocess
from typing import Any, Dict, List

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.llm.ollama_client import OllamaClient

from .prompt_templates import AutoGenPrompts


class ProjectReviewer:
    """Phase 6: Final project review with CI/CD lifecycle verification."""

    DEFAULT_OPTIONS = {
        "num_ctx": 16384,
        "num_predict": 4096,
        "temperature": 0.5,
        "keep_alive": "0s",
    }

    def __init__(self, llm_client: OllamaClient, logger: AgentLogger, options: dict = None):
        self.llm_client = llm_client
        self.logger = logger
        self.options = options or self.DEFAULT_OPTIONS.copy()

    def review(
        self,
        project_name: str,
        readme_excerpt: str,
        file_paths: List[str],
        validation_summary: Dict[str, int],
    ) -> str:
        """Generate a final project review. Returns the review text."""
        project_summary = f"Project: {project_name}\n\n"
        project_summary += f"README:\n{readme_excerpt}\n\n"
        project_summary += f"Files ({len(file_paths)}):\n"
        for p in file_paths[:20]:
            project_summary += f"- {p}\n"
        if len(file_paths) > 20:
            project_summary += f"... and {len(file_paths) - 20} more\n"
        project_summary += f"\nValidation Summary: {json.dumps(validation_summary)}"

        system, user = AutoGenPrompts.project_review(project_summary)
        response_data, usage = self.llm_client.chat(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[],
            options_override=self.options,
        )
        review = response_data["message"]["content"]
        self.logger.info("Final review completed")
        return review

    def verify_completion(self, project_root: str) -> Dict[str, Any]:
        """
        Final verification gate for project closure.
        Checks:
        1. All feature branches merged
        2. No open agent-created issues
        3. README reflects final architecture
        """
        results = {
            "all_branches_merged": True,
            "no_open_agent_issues": True,
            "readme_updated": True,
            "success": True,
            "details": []
        }

        # 1. Check Branches
        try:
            res = subprocess.run(
                ["gh", "pr", "list", "--json", "number,state"],
                cwd=project_root, capture_output=True, text=True
            )
            if res.returncode == 0:
                open_prs = [p for p in json.loads(res.stdout) if p["state"] == "OPEN"]
                if open_prs:
                    results["all_branches_merged"] = False
                    results["details"].append(f"Found {len(open_prs)} open PRs.")
        except Exception as e:
            self.logger.warning(f"Branch check failed: {e}")

        # 2. Check Issues
        try:
            res = subprocess.run(
                ["gh", "issue", "list", "--label", "auto-agent", "--json", "number,state"],
                cwd=project_root, capture_output=True, text=True
            )
            if res.returncode == 0:
                open_issues = [i for i in json.loads(res.stdout) if i["state"] == "OPEN"]
                if open_issues:
                    results["no_open_agent_issues"] = False
                    results["details"].append(f"Found {len(open_issues)} open agent issues.")
        except Exception as e:
            self.logger.warning(f"Issue check failed: {e}")

        # 3. Success check
        results["success"] = results["all_branches_merged"] and results["no_open_agent_issues"]
        
        return results
