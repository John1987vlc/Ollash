"""Unit tests for migrate_preferences() from PreferenceManagerExtended."""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.mark.unit
class TestMigratePreferences:
    def test_migrate_returns_false_when_no_legacy_file(self, tmp_path, mock_logger):
        from backend.utils.core.preference_manager_extended import migrate_preferences

        result = migrate_preferences(tmp_path, mock_logger)
        assert result is False

    def test_migrate_returns_true_when_legacy_file_exists(self, tmp_path, mock_logger):
        from backend.utils.core.preference_manager_extended import migrate_preferences

        legacy_file = tmp_path / ".ollash_preferences.json"
        legacy_file.write_text(json.dumps({"language": "python", "verbosity": "high"}), encoding="utf-8")

        mock_profile = MagicMock()
        mock_profile.custom_settings = {}
        mock_extended = MagicMock()
        mock_extended.get_profile.return_value = mock_profile

        with patch(
            "backend.utils.core.preference_manager_extended.PreferenceManagerExtended",
            return_value=mock_extended,
        ):
            result = migrate_preferences(tmp_path, mock_logger)

        assert result is True
        mock_extended.save_profile.assert_called_once_with(mock_profile)

    def test_migrate_copies_all_keys(self, tmp_path, mock_logger):
        from backend.utils.core.preference_manager_extended import migrate_preferences

        legacy_data = {"lang": "es", "theme": "dark", "font_size": 14}
        legacy_file = tmp_path / ".ollash_preferences.json"
        legacy_file.write_text(json.dumps(legacy_data), encoding="utf-8")

        mock_profile = MagicMock()
        mock_profile.custom_settings = {}
        mock_extended = MagicMock()
        mock_extended.get_profile.return_value = mock_profile

        with patch(
            "backend.utils.core.preference_manager_extended.PreferenceManagerExtended",
            return_value=mock_extended,
        ):
            migrate_preferences(tmp_path, mock_logger, user_id="test_user")

        for key in legacy_data:
            assert key in mock_profile.custom_settings

    def test_migrate_uses_provided_user_id(self, tmp_path, mock_logger):
        from backend.utils.core.preference_manager_extended import migrate_preferences

        legacy_file = tmp_path / ".ollash_preferences.json"
        legacy_file.write_text(json.dumps({"x": 1}), encoding="utf-8")

        mock_profile = MagicMock()
        mock_profile.custom_settings = {}
        mock_extended = MagicMock()
        mock_extended.get_profile.return_value = mock_profile

        with patch(
            "backend.utils.core.preference_manager_extended.PreferenceManagerExtended",
            return_value=mock_extended,
        ):
            migrate_preferences(tmp_path, mock_logger, user_id="alice")

        mock_extended.get_profile.assert_called_once_with("alice")

    def test_migrate_returns_false_on_corrupt_json(self, tmp_path, mock_logger):
        from backend.utils.core.preference_manager_extended import migrate_preferences

        legacy_file = tmp_path / ".ollash_preferences.json"
        legacy_file.write_text("{not valid json}", encoding="utf-8")

        result = migrate_preferences(tmp_path, mock_logger)
        assert result is False
