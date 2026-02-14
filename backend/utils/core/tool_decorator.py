"""Decorator-based tool auto-registration for the Ollash agent framework.

Provides the @ollash_tool decorator that registers tool methods with
their Ollama function schema definitions, enabling dynamic discovery
without manual registration in all_tool_definitions.py or ToolRegistry.
"""

import functools
from typing import Callable, Dict, List, Optional


# Global registries populated by the decorator
_DISCOVERED_TOOLS: Dict[str, Dict] = {}
_DISCOVERED_DEFINITIONS: List[Dict] = []
_ASYNC_ELIGIBLE_TOOLS: List[str] = []


def ollash_tool(
    name: str,
    description: str,
    parameters: Dict,
    toolset_id: str,
    agent_types: Optional[List[str]] = None,
    required: Optional[List[str]] = None,
    is_async_safe: bool = False,
):
    """Decorator that registers a method as an Ollash tool.

    Usage on a tool class method::

        @ollash_tool(
            name="ping_host",
            description="Sends ICMP echo requests to a target host.",
            parameters={
                "host": {"type": "string", "description": "Target host IP or hostname"},
                "count": {"type": "integer", "description": "Number of pings"},
            },
            toolset_id="network_tools",
            agent_types=["network"],
            required=["host"],
            is_async_safe=True
        )
        def ping_host(self, host: str, count: int = 4):
            ...

    Args:
        name: Tool name as exposed to the LLM (must match function schema).
        description: Human-readable description for the LLM.
        parameters: Dict of parameter definitions in Ollama/OpenAI function schema format.
        toolset_id: Identifier of the toolset class (e.g., "network_tools").
        agent_types: List of agent types that should have access to this tool.
        required: List of required parameter names.
        is_async_safe: If True, the tool is eligible for parallel execution.
    """

    def decorator(func: Callable) -> Callable:
        tool_def = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": parameters,
                    "required": required or [],
                },
            },
        }

        _DISCOVERED_TOOLS[name] = {
            "toolset_id": toolset_id,
            "method_name": func.__name__,
            "definition": tool_def,
            "agent_types": agent_types or [],
        }
        _DISCOVERED_DEFINITIONS.append(tool_def)
        
        if is_async_safe:
            _ASYNC_ELIGIBLE_TOOLS.append(name)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._ollash_tool_name = name
        return wrapper

    return decorator


def get_discovered_tool_mapping() -> Dict[str, tuple]:
    """Returns {tool_name: (toolset_id, method_name)} from all decorated tools."""
    return {
        name: (info["toolset_id"], info["method_name"])
        for name, info in _DISCOVERED_TOOLS.items()
    }


def get_discovered_agent_tools() -> Dict[str, List[str]]:
    """Returns {agent_type: [tool_names]} from decorator metadata."""
    agent_tools: Dict[str, List[str]] = {}
    for name, info in _DISCOVERED_TOOLS.items():
        for agent_type in info["agent_types"]:
            agent_tools.setdefault(agent_type, []).append(name)
    return agent_tools


def get_discovered_definitions() -> List[Dict]:
    """Returns all discovered tool definitions in Ollama schema format."""
    return list(_DISCOVERED_DEFINITIONS)


def get_async_eligible_tools() -> List[str]:
    """Returns a list of tool names that are marked as safe for async execution."""
    return list(_ASYNC_ELIGIBLE_TOOLS)
