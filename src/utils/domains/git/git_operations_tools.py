from typing import Any
import re # Added
from src.utils.core.git_manager import GitManager
from src.utils.core.confirmation_manager import ConfirmationManager

class GitOperationsTools:
    def __init__(self, git_manager: GitManager, logger: Any, tool_executor: ConfirmationManager):
        self.git = git_manager
        self.logger = logger
        self.tool_executor = tool_executor

    def git_status(self):
        """Get git status"""
        try:
            branch = self.git.current_branch()
            self.logger.info(f"🌿 Git branch: {branch}")
            return {"ok": True, "branch": branch}
        except Exception as e:
            self.logger.error(f"Git status error: {e}", e)
            return {"ok": False, "error": str(e)}

    def git_commit(self, message: str):
        """Commit with user confirmation, with dynamic approval based on changes."""
        # Get diff stats for staged changes
        diff_stats = self.git.diff_numstat(staged=True)
        
        if not diff_stats["success"]:
            self.logger.warning("Could not get git diff stats, falling back to manual confirmation.")
            if not self.tool_executor._ask_confirmation("git_commit", {"message": message}):
                return {"ok": False, "error": "user_cancelled", "message": "User cancelled the commit"}
        else:
            total_lines_changed = diff_stats["total"]
            modified_critical_files = [f for f in diff_stats["files"]
                                       for pattern in self.tool_executor.critical_paths_patterns
                                       if re.match(pattern, f)]

            if modified_critical_files:
                # Force human gate for critical file changes
                return self.tool_executor.require_human_gate(
                    action_description=f"Attempting to commit changes to critical files: {', '.join(modified_critical_files)}. Manual approval required.",
                    reason="Changes to critical configuration/system files detected."
                )
            elif self.tool_executor.auto_confirm_minor_git_commits and total_lines_changed <= self.tool_executor.git_auto_confirm_lines_threshold:
                self.logger.info(f"Auto-confirming minor git commit (total lines changed: {total_lines_changed}).")
                # Proceed with commit without asking user
            else:
                # Changes too large for auto-confirm, ask user for manual confirmation
                if not self.tool_executor._ask_confirmation("git_commit", {"message": message, "lines_changed": total_lines_changed}):
                    return {"ok": False, "error": "user_cancelled", "message": "User cancelled the commit"}
        
        # Original commit logic
        try:
            result = self.git.create_commit_with_all(message)
            if result.get("success"):
                self.logger.info(f"✅ Committed: {message}")
                return {"ok": True, "message": message, "output": result.get("output")}
            else:
                self.logger.error(f"Git commit failed: {result.get('error')}")
                return {"ok": False, "error": result.get("error")}
        except Exception as e:
            self.logger.error(f"Commit error: {e}", e)
            return {"ok": False, "error": str(e)}

    def git_push(self, remote: str = "origin"):
        """Push with user confirmation"""
        if not self.tool_executor._ask_confirmation("git_push", {"remote": remote}):
            self.logger.info("User cancelled push")
            return {
                "ok": False,
                "error": "user_cancelled",
                "message": "User cancelled the push"
            }
        
        try:
            result = self.git.push(remote)
            if result.get("success"): # GitManager.push returns 'success' not 'ok'
                self.logger.info(f"✅ Pushed to {remote}")
                return {"ok": True, "remote": remote, "output": result.get("output")}
            else:
                self.logger.error(f"Git push failed: {result.get('error')}")
                return {"ok": False, "error": result.get("error")}
        except Exception as e:
            self.logger.error(f"Push error: {e}", e)
            return {"ok": False, "error": str(e)}
