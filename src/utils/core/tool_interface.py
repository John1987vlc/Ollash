from typing import Dict, List, Any
from src.utils.core.all_tool_definitions import get_filtered_tool_definitions
from src.utils.core.confirmation_manager import ToolConfirmationManager

# Backwards-compatible alias so existing imports keep working
ToolExecutor = ToolConfirmationManager