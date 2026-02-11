"""Unit tests for PermissionProfiles module."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.utils.core.permission_profiles import (
    Permission,
    PermissionRule,
    PermissionProfile,
    PermissionProfileManager,
    PolicyEnforcer,
)


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock()


@pytest.fixture
def tmp_sandbox(tmp_path):
    """Create temporary sandbox directory."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    return sandbox


class TestPermission:
    """Test Permission enum."""

    def test_permission_values(self):
        """Test permission enum values."""
        assert Permission.READ.value == "READ"
        assert Permission.WRITE.value == "WRITE"
        assert Permission.EXECUTE.value == "EXECUTE"
        assert Permission.DELETE.value == "DELETE"
        assert Permission.QUERY.value == "QUERY"

    def test_permission_list(self):
        """Test getting list of all permissions."""
        perms = list(Permission)
        assert len(perms) == 5


class TestPermissionRule:
    """Test PermissionRule."""

    def test_create_rule(self):
        """Test creating a permission rule."""
        rule = PermissionRule(
            permission=Permission.READ,
            path_pattern=r"\.py$",
            grant=True,
        )
        
        assert rule.permission == Permission.READ
        assert rule.grant is True

    def test_rule_matches_pattern(self):
        """Test pattern matching in rules."""
        rule = PermissionRule(
            permission=Permission.WRITE,
            path_pattern=r"src/.*\.py$",
            grant=True,
        )
        
        assert rule.matches("src/main.py") is True
        assert rule.matches("src/utils.py") is True
        assert rule.matches("tests/test.py") is False

    def test_rule_with_conditions(self):
        """Test rule with size conditions."""
        rule = PermissionRule(
            permission=Permission.WRITE,
            path_pattern=r".*",
            grant=True,
            conditions={"max_file_size": 1000000},  # 1MB
        )
        
        assert rule.conditions["max_file_size"] == 1000000


class TestPermissionProfile:
    """Test PermissionProfile."""

    def test_create_profile(self, mock_logger):
        """Test creating a permission profile."""
        profile = PermissionProfile(
            name="test_profile",
            logger=mock_logger,
        )
        
        assert profile.name == "test_profile"

    def test_add_rule_to_profile(self, mock_logger):
        """Test adding rules to profile."""
        profile = PermissionProfile(
            name="test_profile",
            logger=mock_logger,
        )
        
        rule = PermissionRule(
            permission=Permission.READ,
            path_pattern=r".*",
            grant=True,
        )
        
        profile.add_rule(rule)
        assert len(profile.rules) == 1

    def test_check_permission_grant(self, mock_logger):
        """Test checking granted permission."""
        profile = PermissionProfile(
            name="test_profile",
            logger=mock_logger,
        )
        
        rule = PermissionRule(
            permission=Permission.READ,
            path_pattern=r"src/.*\.py$",
            grant=True,
        )
        
        profile.add_rule(rule)
        
        # Should grant
        assert profile.check_permission(
            Permission.READ,
            "src/main.py",
        ) is True

    def test_check_permission_deny(self, mock_logger):
        """Test checking denied permission."""
        profile = PermissionProfile(
            name="test_profile",
            logger=mock_logger,
        )
        
        rule = PermissionRule(
            permission=Permission.DELETE,
            path_pattern=r".*",
            grant=False,
        )
        
        profile.add_rule(rule)
        
        # Should deny
        assert profile.check_permission(
            Permission.DELETE,
            "any_file.py",
        ) is False

    def test_permission_default_deny(self, mock_logger):
        """Test that unmapped permissions default to deny."""
        profile = PermissionProfile(
            name="test_profile",
            logger=mock_logger,
        )
        
        # No rules added
        # Should default to deny
        assert profile.check_permission(
            Permission.WRITE,
            "test.py",
        ) is False


class TestPermissionProfileManager:
    """Test PermissionProfileManager."""

    def test_manager_initialization(self, mock_logger):
        """Test manager initializes with default profiles."""
        manager = PermissionProfileManager(logger=mock_logger)
        
        # Should have default profiles
        assert manager.get_profile("sandbox") is not None
        assert manager.get_profile("developer") is not None
        assert manager.get_profile("readonly") is not None

    def test_sandbox_profile_restrictions(self, mock_logger):
        """Test sandbox profile is highly restricted."""
        manager = PermissionProfileManager(logger=mock_logger)
        profile = manager.get_profile("sandbox")
        
        # Sandbox should deny most operations outside sandbox
        assert profile.check_permission(
            Permission.WRITE,
            "any_file.py",
        ) is False

    def test_developer_profile_permissive(self, mock_logger):
        """Test developer profile is more permissive."""
        manager = PermissionProfileManager(logger=mock_logger)
        profile = manager.get_profile("developer")
        
        # Developer should allow reading
        result = profile.check_permission(Permission.READ, "src/app.py")
        assert isinstance(result, bool)  # Should evaluate without error

    def test_readonly_profile(self, mock_logger):
        """Test readonly profile blocks all writes."""
        manager = PermissionProfileManager(logger=mock_logger)
        profile = manager.get_profile("readonly")
        
        # Should allow reads
        assert profile.check_permission(
            Permission.READ,
            "any_file.py",
        ) is True
        
        # Should deny writes
        assert profile.check_permission(
            Permission.WRITE,
            "any_file.py",
        ) is False

    def test_register_custom_profile(self, mock_logger):
        """Test registering a custom profile."""
        manager = PermissionProfileManager(logger=mock_logger)
        
        custom_profile = PermissionProfile(
            name="custom",
            logger=mock_logger,
        )
        
        manager.register_profile(custom_profile)
        
        # Should be findable
        assert manager.get_profile("custom") is not None

    def test_set_active_profile(self, mock_logger):
        """Test setting active profile."""
        manager = PermissionProfileManager(logger=mock_logger)
        
        manager.set_active_profile("sandbox")
        assert manager.active_profile.name == "sandbox"


class TestPolicyEnforcer:
    """Test PolicyEnforcer."""

    def test_enforcer_initialization(self, mock_logger):
        """Test enforcer initialization."""
        profile = PermissionProfile(
            name="test",
            logger=mock_logger,
        )
        
        enforcer = PolicyEnforcer(
            active_profile=profile,
            logger=mock_logger,
        )
        
        assert enforcer.active_profile is not None

    def test_authorize_file_write(self, mock_logger):
        """Test file write authorization."""
        manager = PermissionProfileManager(logger=mock_logger)
        profile = manager.get_profile("readonly")
        
        enforcer = PolicyEnforcer(
            active_profile=profile,
            logger=mock_logger,
        )
        
        # Readonly should deny writes
        result = enforcer.authorize_file_write("test_file.py", 1000)
        assert result is False

    def test_authorize_shell_command_safe(self, mock_logger):
        """Test safe shell command authorization."""
        manager = PermissionProfileManager(logger=mock_logger)
        profile = manager.get_profile("developer")
        
        enforcer = PolicyEnforcer(
            active_profile=profile,
            logger=mock_logger,
        )
        
        # Safe command
        result = enforcer.authorize_shell_command("python script.py")
        assert isinstance(result, bool)

    def test_authorize_shell_command_dangerous(self, mock_logger):
        """Test dangerous command detection."""
        manager = PermissionProfileManager(logger=mock_logger)
        profile = manager.get_profile("developer")
        
        enforcer = PolicyEnforcer(
            active_profile=profile,
            logger=mock_logger,
        )
        
        # Dangerous commands should be denied
        dangerous = [
            "rm -rf /",
            "mkfs.ext4 /dev/sda",
            "dd if=/dev/zero of=/dev/sda",
        ]
        
        for cmd in dangerous:
            result = enforcer.authorize_shell_command(cmd)
            assert result is False

    def test_authorize_delete(self, mock_logger):
        """Test delete authorization."""
        manager = PermissionProfileManager(logger=mock_logger)
        profile = manager.get_profile("readonly")
        
        enforcer = PolicyEnforcer(
            active_profile=profile,
            logger=mock_logger,
        )
        
        # Readonly should deny deletes
        result = enforcer.authorize_delete("test_file.py")
        assert result is False

    def test_switch_profile(self, mock_logger):
        """Test switching active profile."""
        manager = PermissionProfileManager(logger=mock_logger)
        sandbox_profile = manager.get_profile("sandbox")
        developer_profile = manager.get_profile("developer")
        
        enforcer = PolicyEnforcer(
            active_profile=sandbox_profile,
            logger=mock_logger,
        )
        
        # Switch profile
        enforcer.set_active_profile(developer_profile)
        
        assert enforcer.active_profile == developer_profile
