import json
from pathlib import Path
from typing import Dict, List, Any, Optional
import re

class PolicyManager:
    def __init__(self, project_root: Path, logger: Any, config: Dict):
        self.project_root = project_root
        self.logger = logger
        self.config = config
        self.policy_file = self.project_root / "config" / "security_policies.json"
        self.policies: Dict[str, Any] = {}
        self._load_policies()

    def _load_policies(self):
        """Loads security policies from the security_policies.json file."""
        if self.policy_file.exists():
            try:
                with open(self.policy_file, "r", encoding="utf-8") as f:
                    self.policies = json.load(f)
                self.logger.info(f"Security policies loaded from {self.policy_file}")
            except json.JSONDecodeError as e:
                self.logger.error(f"Error decoding policy file {self.policy_file}: {e}")
                self.policies = {} # Reset policies on error
            except Exception as e:
                self.logger.error(f"Unexpected error loading policies from {self.policy_file}: {e}")
                self.policies = {}
        else:
            self.logger.warning(f"No existing security policy file found at {self.policy_file}, using default empty policies.")
            # Optionally, create a default policy file or use hardcoded defaults
            self.policies = {
                "allowed_commands": ["ls", "dir", "cat", "more", "head", "tail", "grep", "find", "python", "pip", "npm", "node", "git", "pytest"],
                "disallowed_patterns": [";", "&&", "||", "|", "`", "$(", ">", "<", ">>", "&"],
                "critical_paths": [".env", "settings.json", "package.json", "requirements.txt", ".git/", ".github/"],
                "path_traversal_regex": r"(\.\./|\.\.\)"
            }
            # Consider saving this default policy if it's the first run
            self._save_policies()

    def _save_policies(self):
        """Saves current policies to the security_policies.json file."""
        try:
            # Ensure the config directory exists
            self.policy_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.policy_file, "w", encoding="utf-8") as f:
                json.dump(self.policies, f, indent=2)
            self.logger.info(f"Security policies saved to {self.policy_file}")
        except Exception as e:
            self.logger.error(f"Error saving policies to {self.policy_file}: {e}")

    def is_command_allowed(self, command: str, args: List[str], current_agent_type: str = "orchestrator") -> bool:
        """
        Checks if a command is allowed based on defined policies.
        Can include agent-type specific rules.
        """
        allowed_commands = self.policies.get("allowed_commands", [])
        disallowed_patterns = self.policies.get("disallowed_patterns", [])
        path_traversal_regex = self.policies.get("path_traversal_regex", r"(\.\./|\.\.\)")

        cmd_parts = command.split(' ')[0] # Get the base command
        
        # 1. Check against disallowed patterns in command itself
        for pattern in disallowed_patterns:
            if pattern in command:
                self.logger.warning(f"Command '{command}' blocked: contains disallowed pattern '{pattern}'")
                return False

        # 2. Check for path traversal in command or args
        if re.search(path_traversal_regex, command):
            self.logger.warning(f"Command '{command}' blocked: contains path traversal pattern")
            return False
        for arg in args:
            if re.search(path_traversal_regex, arg):
                self.logger.warning(f"Argument '{arg}' blocked: contains path traversal pattern")
                return False

        # 3. Check against allowed commands list
        if cmd_parts not in allowed_commands:
            self.logger.warning(f"Command '{cmd_parts}' blocked: not in allowed_commands list for agent type '{current_agent_type}'")
            return False
            
        # Add agent-type specific policies if they were defined in self.policies. For example:
        # agent_specific_allowed = self.policies.get("agent_specific_rules", {}).get(current_agent_type, {}).get("allowed_commands", [])
        # if cmd_parts in agent_specific_allowed:
        #     return True

        self.logger.debug(f"Command '{command}' is allowed.")
        return True

    def is_critical_path(self, file_path: str) -> bool:
        """Checks if a file path matches any critical path patterns."""
        critical_paths = self.policies.get("critical_paths", [])
        for pattern in critical_paths:
            # Use glob.fnmatch for pattern matching or regex
            if re.match(pattern.replace('*', '.*'), file_path): # Basic glob to regex conversion
                return True
        return False

    def get_auto_confirm_thresholds(self, action_type: str) -> Dict[str, Any]:
        """Retrieves auto-confirmation thresholds for a given action type."""
        return self.policies.get("auto_confirm_thresholds", {}).get(action_type, {})

    def get_critical_path_patterns(self) -> List[str]:
        """Retrieves critical path patterns."""
        return self.policies.get("critical_paths", [])
