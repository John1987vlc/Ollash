"""
This file imports all tool modules at application startup.

By importing them here, we ensure that the @ollash_tool decorators are
executed, dynamically registering all tools with the ToolRegistry.
This approach avoids the need for manual registration lists and supports
a plug-and-play architecture for adding new tools.
"""

# Import all tool modules to trigger decorator registration.
# The order does not matter.

from . import (bonus, code, command_line, cybersecurity, git, multimedia,
               network, orchestration, planning, system)
