"""
Preference Manager for the Ollash Agent Framework.

.. deprecated::
    This module is deprecated. Use :class:`PreferenceManagerExtended` from
    ``backend.utils.core.preference_manager_extended`` instead.
    Call :func:`migrate_preferences` to port existing data from
    ``.ollash_preferences.json`` to the new profile-based format.
"""

import json
import warnings
from pathlib import Path
from typing import Any, Dict

from backend.utils.core.system.agent_logger import AgentLogger


class PreferenceManager:
    """Manages user preferences and semantic memory.

    .. deprecated::
        Use ``PreferenceManagerExtended`` for new code. This class will be
        removed in a future release.
    """

    def __init__(self, project_root: Path, logger: AgentLogger):
        """
        Initializes the PreferenceManager.

        Args:
            project_root: The root directory of the project.
            logger: The logger instance.
        """
        warnings.warn(
            "PreferenceManager is deprecated and will be removed in a future release. "
            "Use PreferenceManagerExtended from backend.utils.core.preference_manager_extended. "
            "Run migrate_preferences() to port existing data.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.preferences_file = project_root / ".ollash_preferences.json"
        self.logger = logger
        self.preferences = self._load_preferences()

    def _load_preferences(self) -> Dict[str, Any]:
        """Loads preferences from the JSON file."""
        if self.preferences_file.exists():
            try:
                with open(self.preferences_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                self.logger.error(f"Failed to load preferences from {self.preferences_file}: {e}")
                return {}
        return {}

    def _save_preferences(self):
        """Saves the current preferences to the JSON file."""
        try:
            with open(self.preferences_file, "w", encoding="utf-8") as f:
                json.dump(self.preferences, f, indent=4)
        except IOError as e:
            self.logger.error(f"Failed to save preferences to {self.preferences_file}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Gets a preference value.

        Args:
            key: The preference key.
            default: The default value to return if the key is not found.

        Returns:
            The preference value.
        """
        return self.preferences.get(key, default)

    def set(self, key: str, value: Any):
        """
        Sets a preference value.

        Args:
            key: The preference key.
            value: The preference value.
        """
        self.preferences[key] = value
        self._save_preferences()

    def get_all(self) -> Dict[str, Any]:
        """Returns all preferences."""
        return self.preferences


def migrate_preferences(project_root: Path, logger: AgentLogger, user_id: str = "default") -> bool:
    """Migrate ``.ollash_preferences.json`` data to PreferenceManagerExtended format.

    Reads the legacy flat key-value file and stores every entry as a
    ``custom_settings`` entry in the PreferenceManagerExtended profile for
    ``user_id``.

    Args:
        project_root: Root directory of the project (where ``.ollash_preferences.json`` lives).
        logger: Logger instance for progress messages.
        user_id: Target profile identifier in PreferenceManagerExtended.

    Returns:
        ``True`` if migration was performed, ``False`` if there was nothing to migrate.
    """
    from backend.utils.core.preference_manager_extended import PreferenceManagerExtended

    old_prefs_file = project_root / ".ollash_preferences.json"
    if not old_prefs_file.exists():
        logger.info("migrate_preferences: no legacy file found, nothing to migrate.")
        return False

    try:
        with open(old_prefs_file, "r", encoding="utf-8") as f:
            old_data: Dict[str, Any] = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"migrate_preferences: could not read legacy file: {e}")
        return False

    knowledge_workspace = project_root / ".ollash" / "knowledge_workspace"
    extended = PreferenceManagerExtended(knowledge_workspace)
    profile = extended.get_profile(user_id)

    for key, value in old_data.items():
        profile.custom_settings[key] = value

    extended.save_profile(profile)
    logger.info(
        f"migrate_preferences: migrated {len(old_data)} entries "
        f"from .ollash_preferences.json to PreferenceManagerExtended (user='{user_id}')."
    )
    return True
