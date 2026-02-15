"""Fine-grained permission profiles for secure command execution.

Enhances PolicyManager with granular access control rules,
preventing agents from making unauthorized changes.

Design: Profile-based permissions with regex path matching.
Benefit: Security layer before state-modifying operations.
"""

import re
from enum import Enum
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field

from backend.utils.core.agent_logger import AgentLogger
from backend.core.config_schemas import ToolSettingsConfig # NEW: For accessing auto_confirm_tools


class Permission(Enum):
    """Discrete operation permissions."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELETE = "delete"
    QUERY = "query"


class PermissionProfile:
    """Defines granular access rules for a specific domain/role."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.rules: List["PermissionRule"] = []

    def add_rule(self, rule: "PermissionRule"):
        """Add a permission rule to this profile."""
        self.rules.append(rule)

    def check_permission(
        self,
        permission: Permission,
        resource_path: str,
        context: Optional[Dict] = None,
    ) -> bool:
        """Check if an operation is allowed.

        Args:
            permission: Operation type (READ, WRITE, etc.)
            resource_path: File or directory path
            context: Additional context (e.g., file type, size)

        Returns:
            True if allowed, False otherwise
        """
        for rule in self.rules:
            if rule.matches(permission, resource_path, context):
                return rule.grant

        # Default deny
        return False

    def to_dict(self) -> Dict:
        """Serialize profile to dict."""
        return {
            "name": self.name,
            "description": self.description,
            "rules": [rule.to_dict() for rule in self.rules],
        }


@dataclass
class PermissionRule:
    """Single granular permission rule."""

    permission: Permission
    path_pattern: str  # Regex pattern
    grant: bool = True
    conditions: Dict = field(default_factory=dict)  # E.g., max_file_size
    reason: str = ""

    def matches(
        self,
        permission: Permission,
        resource_path: str,
        context: Optional[Dict] = None,
    ) -> bool:
        """Check if this rule applies to the request."""
        if permission != self.permission:
            return False

        # Match path pattern
        if not re.match(self.path_pattern, resource_path):
            return False

        # Check conditions
        if context:
            if "max_file_size" in self.conditions:
                file_size = context.get("file_size_bytes", 0)
                if file_size > self.conditions["max_file_size"]:
                    return False

            if "allowed_extensions" in self.conditions:
                ext = Path(resource_path).suffix
                if ext not in self.conditions["allowed_extensions"]:
                    return False

        return True

    def to_dict(self) -> Dict:
        return {
            "permission": self.permission.value,
            "path_pattern": self.path_pattern,
            "grant": self.grant,
            "conditions": self.conditions,
            "reason": self.reason,
        }


class PermissionProfileManager:
    """Manages permission profiles for different agent types."""

    def __init__(self, logger: AgentLogger, project_root: Path):
        self.logger = logger
        self.project_root = project_root
        self.profiles: Dict[str, PermissionProfile] = {}
        self._init_default_profiles()

    def _init_default_profiles(self):
        """Initialize standard permission profiles."""
        # Sandbox profile: restricted to ./sandbox/
        sandbox_profile = PermissionProfile(
            name="sandbox",
            description="Restricted to sandbox directory only",
        )
        sandbox_profile.add_rule(
            PermissionRule(
                permission=Permission.READ,
                path_pattern=r"^\.?/?sandbox/.*",
                grant=True,
                reason="Read access within sandbox",
            )
        )
        sandbox_profile.add_rule(
            PermissionRule(
                permission=Permission.WRITE,
                path_pattern=r"^\.?/?sandbox/.*",
                grant=True,
                conditions={"max_file_size": 10 * 1024 * 1024},  # 10MB max
                reason="Write access within sandbox (10MB max file)",
            )
        )
        sandbox_profile.add_rule(
            PermissionRule(
                permission=Permission.DELETE,
                path_pattern=r"^\.?/?sandbox/.*",
                grant=True,
                reason="Delete access within sandbox",
            )
        )
        # Deny everything else
        sandbox_profile.add_rule(
            PermissionRule(
                permission=Permission.WRITE,
                path_pattern=r".*",
                grant=False,
            )
        )
        self.profiles["sandbox"] = sandbox_profile

        # Developer profile: broader access
        dev_profile = PermissionProfile(
            name="developer",
            description="Developer workspace with controlled access outside sandbox",
        )
        dev_profile.add_rule(
            PermissionRule(
                permission=Permission.READ,
                path_pattern=r"^(src|tests|config|prompts|docs|\.)?/?.*",
                grant=True,
                reason="Read access to project files",
            )
        )
        dev_profile.add_rule(
            PermissionRule(
                permission=Permission.WRITE,
                path_pattern=r"^\.?/?sandbox/.*",
                grant=True,
                reason="Write access in sandbox",
            )
        )
        dev_profile.add_rule(
            PermissionRule(
                permission=Permission.WRITE,
                path_pattern=r"^(src|src_new)/?.*",
                grant=True,
                conditions={"allowed_extensions": {".py", ".json", ".yaml", ".md"}},
                reason="Write access to source with file type restrictions",
            )
        )
        dev_profile.add_rule(
            PermissionRule(
                permission=Permission.DELETE,
                path_pattern=r"^\.?/?sandbox/.*",
                grant=True,
                reason="Delete in sandbox only",
            )
        )
        dev_profile.add_rule(
            PermissionRule(
                permission=Permission.EXECUTE,
                path_pattern=r"^(tests|scripts)/?.*\.(py|sh)$",
                grant=True,
                reason="Execute scripts and tests",
            )
        )
        self.profiles["developer"] = dev_profile

        # Read-only profile
        readonly_profile = PermissionProfile(
            name="readonly",
            description="Read-only access to project files",
        )
        readonly_profile.add_rule(
            PermissionRule(
                permission=Permission.READ,
                path_pattern=r".*",
                grant=True,
                reason="Universal read access",
            )
        )
        readonly_profile.add_rule(
            PermissionRule(
                permission=Permission.WRITE,
                path_pattern=r".*",
                grant=False,
                reason="Write access denied",
            )
        )
        self.profiles["readonly"] = readonly_profile

    def register_profile(self, profile: PermissionProfile):
        """Register a custom permission profile."""
        self.profiles[profile.name] = profile
        self.logger.info(f"Registered permission profile: {profile.name}")

    def get_profile(self, name: str) -> Optional[PermissionProfile]:
        """Get a profile by name."""
        return self.profiles.get(name)

    def list_profiles(self) -> List[str]:
        """List all available profile names."""
        return list(self.profiles.keys())

    def check_operation(
        self,
        profile_name: str,
        permission: Permission,
        resource_path: str,
        context: Optional[Dict] = None,
    ) -> Tuple[bool, str]:
        """Check if an operation is permitted under a profile.

        Args:
            profile_name: Name of the permission profile
            permission: Operation type
            resource_path: Target path
            context: Additional context

        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        profile = self.get_profile(profile_name)
        if not profile:
            return False, f"Profile '{profile_name}' not found"

        allowed = profile.check_permission(permission, resource_path, context)

        if allowed:
            return True, f"Operation {permission.value} allowed under {profile_name}"
        else:
            return False, f"Operation {permission.value} denied under {profile_name}"


class PolicyEnforcer:
    """Enforces permission policies on tool execution."""

    def __init__(
        self,
        profile_manager: PermissionProfileManager,
        logger: AgentLogger,
        tool_settings_config: ToolSettingsConfig, # NEW
    ):
        self.profile_manager = profile_manager
        self.logger = logger
        self.tool_settings_config = tool_settings_config # NEW
        self.active_profile = "sandbox"  # Default restrictive
        self._state_modifying_tools = { # NEW: Hardcoded for now, could be dynamic
            "write_file": Permission.WRITE,
            "replace": Permission.WRITE,
            "run_shell_command": Permission.EXECUTE,
            "delete_file": Permission.DELETE,
            "git_commit": Permission.WRITE,
            "git_push": Permission.WRITE,
            "write_todos": Permission.WRITE,
            "remove_dir": Permission.DELETE,
            "move_file": Permission.WRITE,
            "move_dir": Permission.WRITE,
            "copy_file": Permission.WRITE,
            "copy_dir": Permission.WRITE,
            "create_dir": Permission.WRITE,
        }

    def set_active_profile(self, profile_name: str) -> bool:  # noqa: F811
        """Switch to a different permission profile."""
        if profile_name not in self.profile_manager.list_profiles():
            self.logger.error(f"Profile '{profile_name}' not found")
            return False

        self.active_profile = profile_name
        self.logger.info(f"🔐 Switched to permission profile: {profile_name}")
        return True

    def is_auto_approve_enabled(self) -> bool: # NEW METHOD
        """Checks if auto-approval for state-modifying tools is enabled."""
        return self.tool_settings_config.auto_confirm_tools

    def is_tool_state_modifying(self, tool_name: str) -> bool: # NEW METHOD
        """Checks if a given tool is considered state-modifying."""
        return tool_name in self._state_modifying_tools

    def get_permission_for_tool(self, tool_name: str) -> Optional[Permission]: # NEW METHOD
        """Returns the associated permission for a given tool, if it's state-modifying."""
        return self._state_modifying_tools.get(tool_name)

    def authorize_tool_execution(self, tool_name: str, resource_path: str = "", context: Optional[Dict] = None) -> Tuple[bool, str]: # NEW METHOD
        """Authorizes a tool execution, delegating to specific authorize methods if applicable."""
        permission = self.get_permission_for_tool(tool_name)
        if not permission:
            # If not a state-modifying tool, it's implicitly allowed through this mechanism
            return True, "Tool is not considered state-modifying by policy."

        # Delegate to specific authorization methods if they exist and are more granular
        if tool_name == "write_file" or tool_name == "replace":
            return self.authorize_file_write(resource_path, file_size_bytes=context.get("file_size_bytes", 0) if context else 0)
        elif tool_name == "run_shell_command":
            return self.authorize_shell_command(resource_path) # resource_path here is the command itself
        elif tool_name == "delete_file" or tool_name == "remove_dir":
            return self.authorize_delete(resource_path)
        elif tool_name.startswith("git_"): # Generic for git operations
            return self.profile_manager.check_operation(self.active_profile, permission, resource_path or "git_repo", context)
        elif tool_name in ["move_file", "move_dir", "copy_file", "copy_dir", "create_dir"]:
            return self.profile_manager.check_operation(self.active_profile, permission, resource_path, context)

        # Fallback for other state-modifying tools without specific authorize_ methods
        return self.profile_manager.check_operation(self.active_profile, permission, resource_path, context)

    def authorize_file_write(
        self,
        file_path: str,
        file_size_bytes: int = 0,
    ) -> Tuple[bool, str]:
        """Authorize a file write operation."""
        context = {"file_size_bytes": file_size_bytes}
        allowed, reason = self.profile_manager.check_operation(
            self.active_profile,
            Permission.WRITE,
            file_path,
            context,
        )

        if not allowed:
            self.logger.warning(f"⛔ Write denied: {file_path} ({reason})")

        return allowed, reason

    def authorize_shell_command(self, command: str) -> Tuple[bool, str]:
        """Authorize a shell command execution."""
        # Check if command contains dangerous patterns
        dangerous_patterns = [
            r"rm\s+-rf\s+/",  # rm -rf /
            r"dd\s+if=/dev/zero",  # dd format disk
            r"mkfs\.",  # mkfs (format)
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, command):
                return False, f"Dangerous command pattern detected: {pattern}"

        # Default allow if no dangerous patterns
        allowed, reason = self.profile_manager.check_operation(
            self.active_profile,
            Permission.EXECUTE,
            command,
        )

        return allowed, reason

    def is_license_compliant(self, file_path: str) -> bool:
        """Placeholder for license compliance check."""
        return True

    def authorize_delete(self, file_path: str) -> Tuple[bool, str]:
        """Authorize a file deletion."""
        allowed, reason = self.profile_manager.check_operation(
            self.active_profile,
            Permission.DELETE,
            file_path,
        )

        if not allowed:
            self.logger.warning(f"⛔ Delete denied: {file_path} ({reason})")

        return allowed, reason
