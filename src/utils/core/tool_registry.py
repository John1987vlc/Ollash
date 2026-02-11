import importlib
import os
import pkgutil
from typing import Dict, List, Optional

# Import the discovery functions from the decorator module
from .tool_decorator import (
    get_async_eligible_tools,
    get_discovered_agent_tools,
    get_discovered_tool_mapping,
)


def discover_tools(base_path: str = "src/utils/domains"):
    """
    Dynamically discovers and imports all tool modules under the given base path.

    This function iterates through all Python modules in the specified directory
    and its subdirectories, importing them to ensure that any @ollash_tool
    decorators are executed and tools are registered in the global registries.

    Args:
        base_path (str): The starting directory to scan for tool modules.
                         Defaults to "src/utils/domains".
    """
    # Convert the file path to a package path (e.g., "src/utils/domains" -> "src.utils.domains")
    package_path = base_path.replace("/", ".").replace(os.sep, ".")

    # Find the package to get its file path
    package = importlib.util.find_spec(package_path)
    if not package or not package.submodule_search_locations:
        print(f"Warning: Could not find tool modules at package path '{package_path}'.")
        return

    # Walk through all modules and sub-packages
    for _, name, is_pkg in pkgutil.walk_packages(
        package.submodule_search_locations, prefix=f"{package.name}."
    ):
        if not is_pkg:
            try:
                importlib.import_module(name)
                # print(f"Successfully imported tool module: {name}")
            except ImportError as e:
                print(f"Warning: Failed to import tool module {name}. Error: {e}")


class ToolRegistry:
    """Centralized registry for tool-to-toolset mapping and agent-type tool routing.

    This class now dynamically discovers tools decorated with @ollash_tool,
    eliminating the need for manual static registration. To ensure tools are
    discovered, their modules must be imported at application startup.
    """

    # These are now class-level caches populated by the dynamic discovery functions.
    _TOOL_MAPPING: Optional[Dict[str, tuple]] = None
    _AGENT_TOOLS: Optional[Dict[str, List[str]]] = None
    _ASYNC_ELIGIBLE_TOOLS: Optional[List[str]] = None

    @classmethod
    def _initialize_if_needed(cls):
        """Dynamically populates the registries if they haven't been already."""
        if cls._TOOL_MAPPING is None:
            # At this point, all tool modules should have been imported,
            # and the decorators will have populated the global registries.
            cls._TOOL_MAPPING = get_discovered_tool_mapping()
        if cls._AGENT_TOOLS is None:
            cls._AGENT_TOOLS = get_discovered_agent_tools()
        if cls._ASYNC_ELIGIBLE_TOOLS is None:
            cls._ASYNC_ELIGIBLE_TOOLS = get_async_eligible_tools()

    @classmethod
    def get_tool_mapping(cls) -> Dict[str, tuple]:
        """Returns the dynamically discovered tool-to-toolset mapping."""
        cls._initialize_if_needed()
        return cls._TOOL_MAPPING or {}

    @classmethod
    def get_agent_tools(cls) -> Dict[str, List[str]]:
        """Returns the dynamically discovered agent-to-tool mapping."""
        cls._initialize_if_needed()
        return cls._AGENT_TOOLS or {}

    @classmethod
    def get_async_eligible_tools(cls) -> List[str]:
        """Returns the list of tools eligible for asynchronous execution."""
        cls._initialize_if_needed()
        return cls._ASYNC_ELIGIBLE_TOOLS or []

    def get_toolset_for_tool(self, tool_name: str) -> Optional[tuple]:
        """Returns (toolset_identifier, method_name) for a given tool, or None."""
        return self.get_tool_mapping().get(tool_name)

    def get_tools_for_agent(self, agent_type: str) -> List[str]:
        """Returns the list of tool names available for a given agent type."""
        # Ensure default agent types have their base tools.
        base_tools = self.get_agent_tools().get(agent_type, [])
        # Example of adding common tools to all agents if needed:
        # common_tools = self.get_agent_tools().get("common", [])
        # return list(set(base_tools + common_tools))
        return base_tools

    def is_valid_tool(self, tool_name: str) -> bool:
        """Checks if a tool name exists in the registry."""
        return tool_name in self.get_tool_mapping()

    def is_valid_agent_type(self, agent_type: str) -> bool:
        """Checks if an agent type exists in the registry."""
        return agent_type in self.get_agent_tools()

    def get_tool_definitions(self, active_tool_names: List[str]) -> List[Dict]:
        """Returns the OpenAPI-like definitions for the given active tool names."""
        self._initialize_if_needed() # Ensure tools are discovered
        from .tool_decorator import get_discovered_definitions
        
        all_definitions = get_discovered_definitions()
        definitions = []
        for tool_def in all_definitions:
            tool_name = tool_def["function"]["name"]
            if tool_name in active_tool_names:
                definitions.append(tool_def)
        return definitions


# Discover tools immediately when the module is loaded.
# This ensures that all decorators are run before any registry methods are called.
discover_tools()
