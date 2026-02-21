import pytest
from unittest.mock import MagicMock
from backend.utils.core.system.policy_manager import PolicyManager


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def policy_manager(tmp_path, mock_logger):
    config = {}
    return PolicyManager(project_root=tmp_path, logger=mock_logger, config=config)


class TestPolicyManager:
    """Test suite for PolicyManager security rules."""

    def test_init_db(self, policy_manager, tmp_path):
        db_path = tmp_path / ".ollash" / "system.db"
        assert db_path.exists()

    def test_is_command_allowed_success(self, policy_manager):
        assert policy_manager.is_command_allowed("ls", ["-la"]) is True

    def test_is_command_allowed_blocked_command(self, policy_manager):
        assert policy_manager.is_command_allowed("rm", ["-rf", "/"]) is False
        policy_manager.logger.warning.assert_called()

    def test_is_command_allowed_disallowed_pattern(self, policy_manager):
        assert policy_manager.is_command_allowed("ls && cat secret", []) is False

    def test_is_command_allowed_path_traversal(self, policy_manager, tmp_path):
        # Trying to access outside project_root
        assert policy_manager.is_command_allowed("ls", ["../../etc/passwd"]) is False

    def test_is_critical_path(self, policy_manager, tmp_path):
        assert policy_manager.is_critical_path(".env") is True
        assert policy_manager.is_critical_path("src/main.py") is False

    def test_is_critical_path_outside_sandbox(self, policy_manager):
        # Any path that resolves outside project root is considered critical for safety
        assert policy_manager.is_critical_path("../outside.txt") is True

    def test_save_and_load_policies(self, tmp_path, mock_logger):
        pm = PolicyManager(tmp_path, mock_logger, {})
        pm.policies["allowed_commands"].append("special_cmd")
        pm._save_policies()

        # New instance should load from DB
        new_pm = PolicyManager(tmp_path, mock_logger, {})
        assert "special_cmd" in new_pm.policies["allowed_commands"]
