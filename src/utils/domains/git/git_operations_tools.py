from typing import Any
from src.utils.core.git_manager import GitManager
from src.utils.core.tool_interface import ToolExecutor
# Assuming AgentLogger will be passed during initialization
# from src.agents.code_agent import AgentLogger # This will be changed

class GitOperationsTools:
    def __init__(self, git_manager: GitManager, logger: Any, tool_executor: ToolExecutor):
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
        """Commit with user confirmation"""
        if not self.tool_executor._ask_confirmation("git_commit", {"message": message}):
            self.logger.info("User cancelled commit")
            return {
                "ok": False,
                "error": "user_cancelled",
                "message": "User cancelled the commit"
            }
        
        try:
            result = self.git.create_commit_with_all(message)
            if result.get("success"): # GitManager.create_commit_with_all returns 'success' not 'ok'
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
