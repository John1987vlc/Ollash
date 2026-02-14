from typing import Dict, List

from backend.utils.domains.planning.tool_definitions import PLANNING_TOOL_DEFINITIONS
from backend.utils.domains.code.tool_definitions import CODE_TOOL_DEFINITIONS
from backend.utils.domains.command_line.tool_definitions import COMMAND_LINE_TOOL_DEFINITIONS
from backend.utils.domains.git.tool_definitions import GIT_TOOL_DEFINITIONS
from backend.utils.domains.network.tool_definitions import NETWORK_TOOL_DEFINITIONS
from backend.utils.domains.system.tool_definitions import SYSTEM_TOOL_DEFINITIONS
from backend.utils.domains.cybersecurity.tool_definitions import CYBERSECURITY_TOOL_DEFINITIONS
from backend.utils.domains.orchestration.tool_definitions import ORCHESTRATION_TOOL_DEFINITIONS
from backend.utils.domains.bonus.tool_definitions import BONUS_TOOL_DEFINITIONS
from backend.utils.domains.bonus.cowork_tools import COWORK_TOOL_DEFINITIONS

# Aggregated list of all tool definitions (backwards-compatible)
ALL_TOOLS_DEFINITIONS: List[Dict] = [
    *PLANNING_TOOL_DEFINITIONS,
    *CODE_TOOL_DEFINITIONS,
    *COMMAND_LINE_TOOL_DEFINITIONS,
    *GIT_TOOL_DEFINITIONS,
    *NETWORK_TOOL_DEFINITIONS,
    *SYSTEM_TOOL_DEFINITIONS,
    *CYBERSECURITY_TOOL_DEFINITIONS,
    *ORCHESTRATION_TOOL_DEFINITIONS,
    *BONUS_TOOL_DEFINITIONS,
    *COWORK_TOOL_DEFINITIONS,
]


def get_filtered_tool_definitions(tool_names: List[str]) -> List[Dict]:
    """
    Filters the ALL_TOOLS_DEFINITIONS to return only those whose names are in tool_names.
    """
    filtered_definitions = []
    for tool_def in ALL_TOOLS_DEFINITIONS:
        if tool_def["function"]["name"] in tool_names:
            filtered_definitions.append(tool_def)
    return filtered_definitions
