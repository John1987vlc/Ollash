"""Unit tests for PreferenceManager deprecation and migration utility."""

import json
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.mark.unit
class TestPreferenceManagerDeprecation:
    def test_deprecation_warning_raised_on_instantiation(self, tmp_path, mock_logger):
        """PreferenceManager must emit a DeprecationWarning when instantiated."""
        from backend.utils.core.preference_manager import PreferenceManager

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            PreferenceManager(project_root=tmp_path, logger=mock_logger)

        deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
        assert len(deprecation_warnings) >= 1, "Expected at least one DeprecationWarning"
        assert "PreferenceManagerExtended" in str(deprecation_warnings[0].message)

    def test_deprecation_warning_mentions_migration(self, tmp_path, mock_logger):
        from backend.utils.core.preference_manager import PreferenceManager

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            PreferenceManager(project_root=tmp_path, logger=mock_logger)

        msg = str(w[0].message)
        assert "migrate_preferences" in msg

    def test_get_still_works_after_deprecation(self, tmp_path, mock_logger):
        """Deprecated class must remain functional until removed."""
        from backend.utils.core.preference_manager import PreferenceManager

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            pm = PreferenceManager(project_root=tmp_path, logger=mock_logger)
            pm.set("key", "value")
            assert pm.get("key") == "value"

    def test_get_all_returns_dict(self, tmp_path, mock_logger):
        from backend.utils.core.preference_manager import PreferenceManager

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            pm = PreferenceManager(project_root=tmp_path, logger=mock_logger)
            assert isinstance(pm.get_all(), dict)


@pytest.mark.unit
class TestMigratePreferences:
    def test_migrate_returns_false_when_no_legacy_file(self, tmp_path, mock_logger):
        from backend.utils.core.preference_manager import migrate_preferences

        result = migrate_preferences(tmp_path, mock_logger)
        assert result is False

    def test_migrate_returns_true_when_legacy_file_exists(self, tmp_path, mock_logger):
        from backend.utils.core.preference_manager import migrate_preferences

        # Create legacy preferences file
        legacy_file = tmp_path / ".ollash_preferences.json"
        legacy_file.write_text(json.dumps({"language": "python", "verbosity": "high"}), encoding="utf-8")

        # Mock PreferenceManagerExtended at its source module (it is lazily imported inside migrate_preferences)
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
        from backend.utils.core.preference_manager import migrate_preferences

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

        # Every key from legacy must appear in custom_settings
        for key in legacy_data:
            assert key in mock_profile.custom_settings

    def test_migrate_uses_provided_user_id(self, tmp_path, mock_logger):
        from backend.utils.core.preference_manager import migrate_preferences

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
        from backend.utils.core.preference_manager import migrate_preferences

        legacy_file = tmp_path / ".ollash_preferences.json"
        legacy_file.write_text("{not valid json}", encoding="utf-8")

        result = migrate_preferences(tmp_path, mock_logger)
        assert result is False
