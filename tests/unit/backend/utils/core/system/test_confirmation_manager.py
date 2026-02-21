import pytest
from unittest.mock import MagicMock, patch
from backend.utils.core.system.confirmation_manager import ConfirmationManager
from backend.core.config_schemas import ToolSettingsConfig


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_config():
    config = MagicMock(spec=ToolSettingsConfig)
    config.git_auto_confirm_lines_threshold = 10
    config.auto_confirm_minor_git_commits = False
    config.write_auto_confirm_lines_threshold = 5
    config.auto_confirm_minor_writes = False
    config.critical_paths_patterns = [".env"]
    return config


@pytest.fixture
def manager(mock_logger, mock_config):
    return ConfirmationManager(logger=mock_logger, config=mock_config)


class TestConfirmationManager:
    """Test suite for ConfirmationManager safety gates."""

    def test_requires_confirmation(self, manager):
        assert manager._requires_confirmation("write_file") is True
        assert manager._requires_confirmation("read_file") is False

    def test_ask_confirmation_auto_confirm(self, manager):
        manager.auto_confirm = True
        assert manager._ask_confirmation("write_file", {"path": "test.py", "content": "print(1)"}) is True
        manager.logger.info.assert_called_with("Auto-confirming action: write_file")

    def test_ask_confirmation_manual_yes(self, manager):
        manager.auto_confirm = False
        with patch("builtins.input", return_value="yes"):
            details = {"path": "test.py", "content": "line1\nline2", "reason": "test"}
            assert manager._ask_confirmation("write_file", details) is True

    def test_ask_confirmation_manual_no(self, manager):
        manager.auto_confirm = False
        with patch("builtins.input", return_value="no"):
            assert manager._ask_confirmation("delete_file", {"path": "bad.py"}) is False

    def test_ask_confirmation_git_commit(self, manager):
        manager.auto_confirm = False
        with patch("builtins.input", return_value="y"):
            assert manager._ask_confirmation("git_commit", {"message": "feat: test"}) is True
            manager.logger.info.assert_any_call("💾 Message: \x1b[36mfeat: test\x1b[0m")
