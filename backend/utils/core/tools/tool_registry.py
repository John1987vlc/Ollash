import importlib
import os
import pkgutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# Import manager classes
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.analysis.code_analyzer import CodeAnalyzer
from backend.utils.core.command_executor import CommandExecutor
from backend.utils.core.io.file_manager import FileManager
from backend.utils.core.io.git_manager import GitManager

# Import the discovery functions from the decorator module
from .tool_decorator import (
    get_async_eligible_tools,
    get_discovered_agent_tools,
    get_discovered_definitions,
    get_discovered_tool_mapping,
)


def discover_tools(base_path: str = "backend/utils/domains"):
    """
    Dynamically discovers and imports all tool modules under the given base path.

    This function iterates through all Python modules in the specified directory
    and its subdirectories, importing them to ensure that any @ollash_tool
    decorators are executed and tools are registered in the global registries.

    Args:
        base_path (str): The starting directory to scan for tool modules.
                         Defaults to "backend/utils/domains".
    """
    # Convert the file path to a package path (e.g., "backend/utils/domains" -> "backend.utils.domains")
    package_path = base_path.replace("/", ".").replace(os.sep, ".")

    # Find the package to get its file path
    package = importlib.util.find_spec(package_path)
    if not package or not package.submodule_search_locations:
        print(f"Warning: Could not find tool modules at package path '{package_path}'.")
        return

    # Walk through all modules and sub-packages
    for _, name, is_pkg in pkgutil.walk_packages(package.submodule_search_locations, prefix=f"{package.name}."):
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
    It also manages the instantiation and retrieval of callable tool functions.
    """

    _TOOL_MAPPING: Optional[Dict[str, tuple]] = None
    _AGENT_TOOLS: Optional[Dict[str, List[str]]] = None
    _ASYNC_ELIGIBLE_TOOLS: Optional[List[str]] = None

    def __init__(
        self,
        logger: AgentLogger,
        project_root: Path,
        file_manager: FileManager,
        command_executor: CommandExecutor,
        git_manager: GitManager,
        code_analyzer: CodeAnalyzer,
        tool_executor: Any,  # The actual ToolExecutor instance will be passed here.
        confirmation_manager: Any,
    ):
        self.logger = logger
        self.project_root = project_root
        self.file_manager = file_manager
        self.command_executor = command_executor
        self.git_manager = git_manager
        self.code_analyzer = code_analyzer
        self.tool_executor = tool_executor  # The ToolExecutor that will use this registry
        self.confirmation_manager = confirmation_manager

        self._loaded_toolsets: Dict[str, Any] = {}  # To store instances of toolsets

        self._initialize_if_needed()  # Ensure class-level caches are populated

        # This mapping is used to get the class and init_args for each toolset.
        # This is now owned by ToolRegistry.
        self._toolset_configs = {
            "file_system_tools": {
                "class_path": "backend.utils.domains.code.file_system_tools.FileSystemTools",
                "init_args": {
                    "project_root": self.project_root,
                    "file_manager": self.file_manager,
                    "logger": self.logger,
                    "tool_executor": self.confirmation_manager,
                },
            },
            "code_analysis_tools": {
                "class_path": "backend.utils.domains.code.code_analysis_tools.CodeAnalysisTools",
                "init_args": {
                    "project_root": self.project_root,
                    "code_analyzer": self.code_analyzer,
                    "command_executor": self.command_executor,
                    "logger": self.logger,
                },
            },
            "command_line_tools": {
                "class_path": "backend.utils.domains.command_line.command_line_tools.CommandLineTools",
                "init_args": {
                    "command_executor": self.command_executor,
                    "logger": self.logger,
                },
            },
            "git_operations_tools": {
                "class_path": "backend.utils.domains.git.git_operations_tools.GitOperationsTools",
                "init_args": {
                    "git_manager": self.git_manager,
                    "logger": self.logger,
                    "tool_executor": self.confirmation_manager,
                },
            },
            "planning_tools": {
                "class_path": "backend.utils.domains.planning.planning_tools.PlanningTools",
                "init_args": {
                    "logger": self.logger,
                    "project_root": self.project_root,
                    "agent_instance": None,
                },  # agent_instance set dynamically
            },
            "network_tools": {
                "class_path": "backend.utils.domains.network.network_tools.NetworkTools",
                "init_args": {
                    "command_executor": self.command_executor,
                    "logger": self.logger,
                },
            },
            "system_tools": {
                "class_path": "backend.utils.domains.system.system_tools.SystemTools",
                "init_args": {
                    "command_executor": self.command_executor,
                    "file_manager": self.file_manager,
                    "logger": self.logger,
                    "agent_instance": None,
                },  # agent_instance set dynamically
            },
            "cybersecurity_tools": {
                "class_path": "backend.utils.domains.cybersecurity.cybersecurity_tools.CybersecurityTools",
                "init_args": {
                    "command_executor": self.command_executor,
                    "file_manager": self.file_manager,
                    "logger": self.logger,
                },
            },
            "orchestration_tools": {
                "class_path": "backend.utils.domains.orchestration.orchestration_tools.OrchestrationTools",
                "init_args": {"logger": self.logger},
            },
            "image_generator_tools": {
                "class_path": "backend.utils.domains.multimedia.image_generation_tools.ImageGeneratorTools",
                "init_args": {"logger": self.logger, "config": None},
            },
            "advanced_code_tools": {
                "class_path": "backend.utils.domains.code.advanced_code_tools.AdvancedCodeTools",
                "init_args": {
                    "project_root": self.project_root,
                    "code_analyzer": self.code_analyzer,
                    "command_executor": self.command_executor,
                    "logger": self.logger,
                },
            },
            "advanced_system_tools": {
                "class_path": "backend.utils.domains.system.advanced_system_tools.AdvancedSystemTools",
                "init_args": {
                    "command_executor": self.command_executor,
                    "logger": self.logger,
                },
            },
            "advanced_network_tools": {
                "class_path": "backend.utils.domains.network.advanced_network_tools.AdvancedNetworkTools",
                "init_args": {
                    "command_executor": self.command_executor,
                    "logger": self.logger,
                },
            },
            "advanced_cybersecurity_tools": {
                "class_path": "backend.utils.domains.cybersecurity.advanced_cybersecurity_tools.AdvancedCybersecurityTools",
                "init_args": {
                    "command_executor": self.command_executor,
                    "file_manager": self.file_manager,
                    "logger": self.logger,
                },
            },
            "bonus_tools": {
                "class_path": "backend.utils.domains.bonus.bonus_tools.BonusTools",
                "init_args": {"logger": self.logger},
            },
        }

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
        self._initialize_if_needed()  # Ensure tools are discovered

        all_definitions = get_discovered_definitions()
        definitions = []
        for tool_def in all_definitions:
            tool_name = tool_def["function"]["name"]
            if tool_name in active_tool_names:
                definitions.append(tool_def)
        return definitions

    def get_callable_tool_function(self, tool_name: str, agent_instance: Any) -> Callable:
        """
        Retrieves the callable function for a given tool, lazily instantiating its toolset if necessary.
        """
        toolset_identifier, method_name_in_toolset = self.get_tool_mapping().get(tool_name)

        if toolset_identifier not in self._loaded_toolsets:
            toolset_config = self._toolset_configs.get(toolset_identifier)
            if not toolset_config:
                raise ValueError(f"Toolset configuration for '{toolset_identifier}' not found in registry.")

            class_path = toolset_config["class_path"]
            module_name, class_name = class_path.rsplit(".", 1)

            # Dynamically import the module and get the class
            try:
                module = importlib.import_module(module_name)
                toolset_class = getattr(module, class_name)
            except (ImportError, AttributeError) as e:
                raise RuntimeError(f"Failed to dynamically load toolset class {class_path}: {e}")

            init_args = toolset_config["init_args"].copy()  # Use a copy to avoid modifying original

            # Dynamically set agent_instance for toolsets that require it
            if toolset_identifier == "planning_tools" or toolset_identifier == "system_tools":
                init_args["agent_instance"] = agent_instance

            self.logger.debug(
                f"Lazily instantiating toolset: {toolset_identifier} from {class_path} with args: {init_args}"
            )
            self._loaded_toolsets[toolset_identifier] = toolset_class(**init_args)

        toolset_instance = self._loaded_toolsets[toolset_identifier]
        tool_func = getattr(toolset_instance, method_name_in_toolset, None)

        if not tool_func:
            raise AttributeError(f"Method '{method_name_in_toolset}' not found in toolset '{toolset_identifier}'.")

        return tool_func


# Discover tools immediately when the module is loaded.
# This ensures that all decorators are run before any registry methods are called.
discover_tools()
