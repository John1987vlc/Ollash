"""
Preference Manager for the Ollash Agent Framework.

This module provides a class to manage user preferences and semantic memory.
It can store, retrieve, and update user preferences, and can be used to
personalize the agent's behavior.
"""

import json
from pathlib import Path
from typing import Any, Dict

from backend.utils.core.agent_logger import AgentLogger


class PreferenceManager:
    """Manages user preferences and semantic memory."""

    def __init__(self, project_root: Path, logger: AgentLogger):
        """
        Initializes the PreferenceManager.

        Args:
            project_root: The root directory of the project.
            logger: The logger instance.
        """
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
                self.logger.error(
                    f"Failed to load preferences from {self.preferences_file}: {e}"
                )
                return {}
        return {}

    def _save_preferences(self):
        """Saves the current preferences to the JSON file."""
        try:
            with open(self.preferences_file, "w", encoding="utf-8") as f:
                json.dump(self.preferences, f, indent=4)
        except IOError as e:
            self.logger.error(
                f"Failed to save preferences to {self.preferences_file}: {e}"
            )

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
