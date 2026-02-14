from typing import Dict, List, Any
from colorama import Fore, Style
import re

class ConfirmationManager:
    """Manages confirmation gates for state-modifying tools."""
    MODIFY_ACTIONS = {"write_file", "delete_file", "git_commit", "git_push"}

    def __init__(self, logger: Any, config: Dict = None, auto_confirm: bool = False, tool_registry: Any = None):
        self.logger = logger
        self.config = config if config is not None else {}
        self.auto_confirm = auto_confirm
        self.tool_registry = tool_registry

        self.git_auto_confirm_lines_threshold: int = self.config.get("git_auto_confirm_lines_threshold", 5)
        self.auto_confirm_minor_git_commits: bool = self.config.get("auto_confirm_minor_git_commits", False)

        self.write_auto_confirm_lines_threshold: int = self.config.get("write_auto_confirm_lines_threshold", 10)
        self.auto_confirm_minor_writes: bool = self.config.get("auto_confirm_minor_writes", False)

        self.critical_paths_patterns: List[str] = self.config.get("critical_paths_patterns", [
            r".*\.env$",
            r".*settings\.json$",
            r".*\.yaml$", r".*\.yml$",
            r".*dockerfile.*",
            r".*\.sh$", r".*\.ps1$",
            r"^\.github/workflows/.*$"
        ])

    def get_tool_definitions(self, active_tool_names: List[str]) -> List[Dict]:
        """
        Retrieves the tool definitions for the currently active tools from the ToolRegistry.
        """
        if self.tool_registry is None:
            raise ValueError("ToolRegistry not set in ToolConfirmationManager.")
        from backend.utils.core.tool_registry import ToolRegistry # Import here to avoid circular dependency
        return self.tool_registry.get_tool_definitions(active_tool_names)

    def _requires_confirmation(self, tool_name: str) -> bool:
        """Check if a tool requires user confirmation"""
        return tool_name in self.MODIFY_ACTIONS

    def _ask_confirmation(self, action: str, details: Dict) -> bool:
        """Ask user for confirmation"""
        if self.auto_confirm:
            self.logger.info(f"Auto-confirming action: {action}")
            return True

        self.logger.info(f"\n{Fore.YELLOW}{'='*60}")
        self.logger.info(f"⚠️  CONFIRMATION REQUIRED: {action}")
        self.logger.info(f"{'='*60}{Style.RESET_ALL}")
        
        if action == "write_file":
            self.logger.info(f"📝 File: {Fore.CYAN}{details['path']}{Style.RESET_ALL}")
            self.logger.info(f"📋 Reason: {details.get('reason', 'N/A')}")
            self.logger.info(f"📏 Size: {len(details['content'])} characters")
            
            lines = details['content'].split('\n')
            preview_lines = min(10, len(lines))
            self.logger.info(f"\n📄 Preview (first {preview_lines} lines):")
            self.logger.info("-" * 60)
            for i, line in enumerate(lines[:preview_lines], 1):
                self.logger.info(f"{Fore.WHITE}{i:3}: {line}{Style.RESET_ALL}")
            if len(lines) > preview_lines:
                self.logger.info(f"{Fore.YELLOW}... ({len(lines) - preview_lines} more lines){Style.RESET_ALL}")
            self.logger.info("-" * 60)
            
        elif action == "delete_file":
            self.logger.info(f"🗑️  File: {Fore.RED}{details['path']}{Style.RESET_ALL}")
            self.logger.info(f"📋 Reason: {details.get('reason', 'N/A')}")
            
        elif action == "git_commit":
            self.logger.info(f"💾 Message: {Fore.CYAN}{details['message']}{Style.RESET_ALL}")
            
        elif action == "git_push":
            self.logger.info(f"🚀 Remote: {Fore.CYAN}{details.get('remote', 'origin')}{Style.RESET_ALL}")
        
        self.logger.info(f"{Fore.YELLOW}{'='*60}{Style.RESET_ALL}")
        
        while True:
            response = input(f"{Fore.GREEN}Proceed? (yes/no/view): {Style.RESET_ALL}").strip().lower()
            if response in ['yes', 'y', 'si', 's']:
                return True
            elif response in ['no', 'n']:
                return False
            elif response in ['view', 'v'] and action == "write_file":
                self.logger.info(f"\n{Fore.CYAN}{'='*60}")
                self.logger.info("FULL CONTENT:")
                self.logger.info(f"{'='*60}{Style.RESET_ALL}")
                print(details['content'])
                self.logger.info(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
            else:
                self.logger.info(f"{Fore.RED}Please answer 'yes', 'no', or 'view'{Style.RESET_ALL}")
