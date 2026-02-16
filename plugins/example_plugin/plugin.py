"""
Example Plugin for Ollash

Demonstrates how to create a plugin that registers custom tools
with the Ollash tool system.
"""

from typing import Any, Dict, List

from backend.utils.core.plugin_interface import OllashPlugin


class ExamplePlugin(OllashPlugin):
    """A sample plugin that adds a 'hello_world' tool."""

    def get_id(self) -> str:
        return "example_plugin"

    def get_name(self) -> str:
        return "Example Plugin"

    def get_version(self) -> str:
        return "1.0.0"

    def get_description(self) -> str:
        return "A demonstration plugin that provides a hello_world tool."

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "hello_world",
                    "description": "Returns a greeting message. Used to test plugin functionality.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name to greet",
                            }
                        },
                        "required": ["name"],
                    },
                },
            }
        ]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        if tool_name == "hello_world":
            name = arguments.get("name", "World")
            return f"Hello, {name}! This response comes from the Example Plugin."
        return f"Unknown tool: {tool_name}"

    def on_load(self) -> None:
        pass

    def on_unload(self) -> None:
        pass
