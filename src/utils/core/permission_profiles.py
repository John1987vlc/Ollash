"""Fine-grained permission profiles for secure command execution.

Enhances PolicyManager with granular access control rules,
preventing agents from making unauthorized changes.

Design: Profile-based permissions with regex path matching.
Benefit: Security layer before state-modifying operations.
"""

import re
from enum import Enum
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field

from src.utils.core.agent_logger import AgentLogger


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
    ):
        self.profile_manager = profile_manager
        self.logger = logger
        self.active_profile = "sandbox"  # Default restrictive

    def set_active_profile(self, profile_name: str) -> bool:
        """Switch to a different permission profile."""
        if profile_name not in self.profile_manager.list_profiles():
            self.logger.error(f"Profile '{profile_name}' not found")
            return False

        self.active_profile = profile_name
        self.logger.info(f"🔐 Switched to permission profile: {profile_name}")
        return True

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


from typing import Tuple
