"""
Plugin Interface for Ollash Tool System

Defines the abstract base class that third-party plugins must implement
to integrate custom tool domains into the Ollash framework.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class OllashPlugin(ABC):
    """Abstract base class for Ollash plugins.

    Third-party developers implement this interface to add new tool domains.

    Example::

        class MyPlugin(OllashPlugin):
            def get_id(self) -> str:
                return "my_custom_domain"

            def get_name(self) -> str:
                return "My Custom Domain Tools"

            def get_version(self) -> str:
                return "1.0.0"

            def get_tool_definitions(self) -> List[Dict]:
                return [
                    {
                        "type": "function",
                        "function": {
                            "name": "my_tool",
                            "description": "Does something useful",
                            "parameters": {
                                "type": "object",
                                "properties": {"input": {"type": "string"}},
                                "required": ["input"],
                            },
                        },
                    }
                ]

            def get_toolset_configs(self) -> List[Dict]:
                return [
                    {
                        "toolset_id": "my_tools",
                        "class_path": "plugins.my_plugin.tools.MyTools",
                        "init_args": {},
                        "agent_types": ["orchestrator", "code"],
                    }
                ]
    """

    @abstractmethod
    def get_id(self) -> str:
        """Unique plugin identifier (e.g., 'database_tools')."""

    @abstractmethod
    def get_name(self) -> str:
        """Human-readable plugin name."""

    @abstractmethod
    def get_version(self) -> str:
        """Plugin version string (semver recommended)."""

    @abstractmethod
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return Ollama-compatible function schema definitions.

        Each entry should follow the format::

            {
                "type": "function",
                "function": {
                    "name": "tool_name",
                    "description": "Tool description",
                    "parameters": {
                        "type": "object",
                        "properties": {...},
                        "required": [...]
                    }
                }
            }
        """

    @abstractmethod
    def get_toolset_configs(self) -> List[Dict[str, Any]]:
        """Return toolset configuration for ToolRegistry integration.

        Each entry should contain::

            {
                "toolset_id": str,       # Unique toolset identifier
                "class_path": str,       # Fully-qualified Python class path
                "init_args": dict,       # Constructor arguments
                "agent_types": list,     # Which agent types can use these tools
            }
        """

    def get_agent_types(self) -> List[str]:
        """Return agent types this plugin supports. Derived from toolset configs."""
        types = set()
        for cfg in self.get_toolset_configs():
            types.update(cfg.get("agent_types", []))
        return list(types)

    def on_load(self) -> None:
        """Called when the plugin is loaded. Override for initialization logic."""

    def on_unload(self) -> None:
        """Called when the plugin is unloaded. Override for cleanup logic."""

    def get_dependencies(self) -> List[str]:
        """Return list of required pip packages. Override if plugin needs extras."""
        return []

    def get_metadata(self) -> Dict[str, Any]:
        """Return plugin metadata for display/debugging."""
        return {
            "id": self.get_id(),
            "name": self.get_name(),
            "version": self.get_version(),
            "agent_types": self.get_agent_types(),
            "dependencies": self.get_dependencies(),
        }
