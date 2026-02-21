import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from backend.utils.core.system.db.sqlite_manager import DatabaseManager
from backend.utils.core.analysis.license_checker import LicenseChecker


class PolicyManager:
    def __init__(self, project_root: Path, logger: Any, config: Dict):
        self.project_root = project_root
        self.logger = logger
        self.config = config

        # Initialize SQLite DB
        db_path = self.project_root / ".ollash" / "system.db"
        self.db = DatabaseManager(db_path)
        self._init_db()

        self.policies: Dict[str, Any] = {}
        self._load_policies()
        self.license_checker = LicenseChecker(self.logger, self.config)

    def _init_db(self):
        """Initialize the policies table."""
        with self.db.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS policies (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    def _load_policies(self):
        """Loads security policies from the database."""
        try:
            rows = self.db.fetch_all("SELECT key, value FROM policies")
            if rows:
                for row in rows:
                    try:
                        self.policies[row["key"]] = json.loads(row["value"])
                    except json.JSONDecodeError:
                        self.logger.warning(f"Failed to decode policy {row['key']}")
                self.logger.info("Security policies loaded from system.db")
            else:
                self.logger.warning("No existing security policies found in DB, using defaults.")
                self._set_defaults()
                self._save_policies()
        except Exception as e:
            self.logger.error(f"Error loading policies from DB: {e}")
            self._set_defaults()

    def _set_defaults(self):
        """Sets default policies."""
        self.policies = {
            "allowed_commands": [
                "ls",
                "dir",
                "cat",
                "more",
                "head",
                "tail",
                "grep",
                "find",
                "git",
                "pytest",
                "ruff",
                "mypy",
            ],
            "restricted_commands": {
                "python": ["-m", "pytest", "-c"],
                "pip": ["install", "list", "show", "freeze"],
                "npm": ["install", "list", "run", "test"],
                "node": [],
            },
            "disallowed_patterns": [";", "&&", "||", "`", "$(", ">>", "&"],
            "critical_paths": [".env", "settings.json", "package.json", "requirements.txt", ".git/", ".github/"],
            "path_traversal_regex": r"(\.\./|\.\.)",
        }

    def _save_policies(self):
        """Saves current policies to the database."""
        try:
            from datetime import datetime

            now = datetime.now().isoformat()

            for key, value in self.policies.items():
                self.db.upsert("policies", {"key": key, "value": json.dumps(value), "updated_at": now}, ["key"])
            self.logger.info("Security policies saved to system.db")
        except Exception as e:
            self.logger.error(f"Error saving policies to DB: {e}")

    def is_license_compliant(self, file_path: Path) -> bool:
        """Checks if the license of a file is compliant."""
        return self.license_checker.check_file_license(file_path)

    def is_command_allowed(self, command: str, args: List[str], current_agent_type: str = "orchestrator") -> bool:
        """
        Checks if a command is allowed based on defined policies,
        including path validation to prevent symlink traversal outside project_root.
        """
        allowed_commands = self.policies.get("allowed_commands", [])
        disallowed_patterns = self.policies.get("disallowed_patterns", [])
        path_traversal_regex = self.policies.get("path_traversal_regex", r"(\.\./|\.\.)")

        cmd_parts = command.split(" ")[0]  # Get the base command

        # 1. Check against disallowed patterns in command itself
        for pattern in disallowed_patterns:
            if pattern in command:
                self.logger.warning(f"Command '{command}' blocked: contains disallowed pattern '{pattern}'")
                return False

        # 2. Path Traversal & Symlink Validation (before other checks)
        for arg in args:
            if "/" in arg or "\\" in arg or arg.startswith("..") or arg.startswith("./"):
                try:
                    # Construct an absolute path relative to the project_root (sandbox)
                    abs_path = self.project_root / arg

                    # Resolve symlinks and normalize the path
                    resolved_path = Path(os.path.realpath(str(abs_path)))

                    # Check if the resolved path is outside the project_root
                    if not resolved_path.is_relative_to(self.project_root):
                        self.logger.warning(
                            f"Argument '{arg}' blocked: resolved path '{resolved_path}' is outside sandbox '{self.project_root}'"
                        )
                        return False
                except Exception as e:
                    self.logger.warning(f"Error resolving path for argument '{arg}': {e}. Blocking command for safety.")
                    return False

        # 3. Check for path traversal regex in original command and args (redundant but extra safety)
        if re.search(path_traversal_regex, command):
            self.logger.warning(f"Command '{command}' blocked: contains path traversal pattern (regex)")
            return False
        for arg in args:
            if re.search(path_traversal_regex, arg):
                self.logger.warning(f"Argument '{arg}' blocked: contains path traversal pattern (regex)")
                return False

        # 4. Check against allowed commands list
        if cmd_parts not in allowed_commands:
            self.logger.warning(
                f"Command '{cmd_parts}' blocked: not in allowed_commands list for agent type '{current_agent_type}'"
            )
            return False

        self.logger.debug(f"Command '{command}' is allowed.")
        return True

    def is_critical_path(self, file_path: str) -> bool:
        """Checks if a file path matches any critical path patterns."""
        critical_paths = self.policies.get("critical_paths", [])
        # Resolve the real path of the file_path being checked
        try:
            abs_file_path = self.project_root / file_path
            resolved_file_path = Path(os.path.realpath(str(abs_file_path)))

            # Ensure the resolved path is within the project root before checking critical status
            if not resolved_file_path.is_relative_to(self.project_root):
                self.logger.warning(
                    f"Critical path check: Resolved path '{resolved_file_path}' is outside sandbox '{self.project_root}'. Treating as critical."
                )
                return True  # Out-of-sandbox paths are inherently critical

            # Then compare the resolved path to critical path patterns
            for pattern in critical_paths:
                # Need to use glob.fnmatch or similar for proper pattern matching if patterns contain wildcards
                # For simplicity, if pattern is a direct path, compare. If it's a regex, use re.match
                if "*" in pattern or "?" in pattern:  # Assume glob-like pattern
                    if resolved_file_path.match(pattern):
                        self.logger.debug(
                            f"Path '{file_path}' resolved to '{resolved_file_path}' matches critical pattern '{pattern}'."
                        )
                        return True
                else:  # Assume direct path or regex-like without glob
                    # Use relative path for matching against patterns defined as such (e.g., "settings.json")
                    relative_resolved_path = resolved_file_path.relative_to(self.project_root)
                    if str(relative_resolved_path) == pattern or re.match(pattern, str(relative_resolved_path)):
                        self.logger.debug(
                            f"Path '{file_path}' resolved to '{resolved_file_path}' matches critical pattern '{pattern}'."
                        )
                        return True
        except Exception as e:
            self.logger.error(f"Error during critical path check for '{file_path}': {e}. Blocking for safety.")
            return True  # Error during resolution should be considered critical for safety
        return False

    def get_auto_confirm_thresholds(self, action_type: str) -> Dict[str, Any]:
        """Retrieves auto-confirmation thresholds for a given action type."""
        return self.policies.get("auto_confirm_thresholds", {}).get(action_type, {})

    def get_critical_path_patterns(self) -> List[str]:
        """Retrieves critical path patterns."""
        return self.policies.get("critical_paths", [])
