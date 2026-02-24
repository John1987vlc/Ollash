"""
Base class for all domain agents in the Agent-per-Domain architecture.

Provides:
- ``REQUIRED_TOOLS`` class attribute for Dynamic Tool Injection.
- ``_get_tool_prompt_section()`` — builds a minimal system-prompt section
  that lists only the tools the agent actually needs, reducing LLM token usage.
- ``_publish_event()`` convenience wrapper.
- Standardised ``run(node, blackboard)`` abstract interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, TYPE_CHECKING

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.event_publisher import EventPublisher

if TYPE_CHECKING:
    from backend.agents.orchestrators.blackboard import Blackboard
    from backend.agents.orchestrators.task_dag import TaskNode
    from backend.agents.orchestrators.tool_dispatcher import ToolDispatcher


# Human-readable descriptions used in LLM system prompts.
_TOOL_DESCRIPTIONS: Dict[str, str] = {
    "dependency_graph": "Analyse file import relationships and build a dependency graph",
    "structure_generator": "Generate a project directory/file structure from a description",
    "file_content_generator": "Generate complete file content from an implementation plan",
    "code_patcher": "Apply targeted edits or difflib-based merges to existing files",
    "rag_context_selector": "Select semantically relevant context files for RAG",
    "infra_generator": "Generate Docker, CI/CD, and infrastructure-as-code files",
    "cicd_healer": "Detect and propose fixes for CI/CD pipeline failures",
    "vulnerability_scanner": "Scan source code for OWASP Top-10 and custom security rules",
    "code_quarantine": "Isolate files containing critical vulnerabilities",
    "parallel_file_generator": "Generate multiple small files in a single batch LLM call",
    "locked_file_manager": "Write files with per-path asyncio locks to prevent conflicts",
}


class BaseDomainAgent(ABC):
    """Abstract base class for all four domain agents.

    Subclasses must:
    - Set ``REQUIRED_TOOLS`` to the minimal list of tool names they use.
    - Set a unique ``agent_id`` string (used in events and Blackboard writes).
    - Implement ``run(node, blackboard)``.
    """

    REQUIRED_TOOLS: List[str] = []
    agent_id: str = "base"

    def __init__(
        self,
        event_publisher: EventPublisher,
        logger: AgentLogger,
        tool_dispatcher: "ToolDispatcher",
    ) -> None:
        self._event_publisher = event_publisher
        self._logger = logger
        self._tool_dispatcher = tool_dispatcher

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def run(
        self,
        node: "TaskNode",
        blackboard: "Blackboard",
    ) -> Any:
        """Execute the work defined by *node*, reading/writing via *blackboard*.

        Args:
            node: The TaskNode containing task_data, dependencies, and metadata.
            blackboard: The shared Blackboard for inter-agent communication.

        Returns:
            Agent-specific result (e.g. Dict[str, str] of generated files).
        """

    # ------------------------------------------------------------------
    # Dynamic Tool Injection
    # ------------------------------------------------------------------

    def _get_tool_prompt_section(self) -> str:
        """Build the '## AVAILABLE TOOLS' system-prompt section.

        Returns an empty string when ``REQUIRED_TOOLS`` is empty, so this
        method is safe to call even for agents that don't use it.  The
        generated section is injected into the LLM's system prompt, ensuring
        the model only sees tools it actually needs (reduces token waste).
        """
        if not self.REQUIRED_TOOLS:
            return ""
        lines = ["## AVAILABLE TOOLS"]
        for tool_name in self.REQUIRED_TOOLS:
            desc = _TOOL_DESCRIPTIONS.get(tool_name, tool_name)
            lines.append(f"- **{tool_name}**: {desc}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------

    def _publish_event(self, event_type: str, **kwargs: Any) -> None:
        """Publish an event with this agent's id attached."""
        self._event_publisher.publish(event_type, agent_id=self.agent_id, **kwargs)

    def _log_info(self, msg: str) -> None:
        self._logger.info(f"[{self.agent_id}] {msg}")

    def _log_debug(self, msg: str) -> None:
        self._logger.debug(f"[{self.agent_id}] {msg}")

    def _log_error(self, msg: str) -> None:
        self._logger.error(f"[{self.agent_id}] {msg}")

    def _log_warning(self, msg: str) -> None:
        self._logger.warning(f"[{self.agent_id}] {msg}")
