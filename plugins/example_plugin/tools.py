"""
Tool implementations for the Example Plugin.

Separates tool logic from plugin registration for cleaner architecture.
"""

from typing import Any, Dict


def hello_world(name: str = "World") -> Dict[str, Any]:
    """A simple greeting tool for testing plugin integration."""
    return {
        "message": f"Hello, {name}! This response comes from the Example Plugin.",
        "plugin": "example_plugin",
        "version": "1.0.0",
    }
