"""Centralized type definitions for the Ollash framework.

Provides TypedDict, Literal, and Protocol types for strict static typing
across the codebase. Import from here for consistent type annotations.
"""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

from typing_extensions import Protocol, TypedDict, runtime_checkable


# --------------- Literal Types ---------------

PhaseOutcome = Literal["success", "partial", "failure"]
"""Outcome of an episodic memory entry or phase execution."""

AgentType = Literal["orchestrator", "code", "network", "system", "cybersecurity"]
"""Available agent specialization types."""

SeverityLevel = Literal["critical", "high", "medium", "low", "info"]
"""Vulnerability or issue severity levels."""

SandboxLevel = Literal["limited", "full", "none"]
"""Security sandbox levels for command execution."""

LLMProviderType = Literal["ollama", "openai_compatible"]
"""Supported LLM provider types."""

PhaseCategory = Literal["generation", "review", "validation", "infrastructure"]
"""Categories for grouping pipeline phases."""


# --------------- TypedDict Definitions ---------------


class PhaseResultDict(TypedDict):
    """Return type of a phase execution."""

    generated_files: Dict[str, str]
    structure: Dict[str, Any]
    file_paths: List[str]


class ExecutionPlanDict(TypedDict, total=False):
    """Serialized execution plan state."""

    project_name: str
    milestones: List[Dict[str, Any]]
    progress: float
    status: str
    is_existing_project: bool


class ToolCallDict(TypedDict):
    """A single tool call from the LLM."""

    name: str
    arguments: Dict[str, Any]


class ToolResultDict(TypedDict, total=False):
    """Result of a tool execution."""

    name: str
    result: str
    success: bool
    error: Optional[str]


class CostReportEntryDict(TypedDict, total=False):
    """Token cost entry for a model or phase."""

    model: str
    phase: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    latency_ms: float


class VulnerabilityDict(TypedDict, total=False):
    """A detected security vulnerability."""

    rule_id: str
    severity: str
    description: str
    file_path: str
    line_number: int
    fix_suggestion: str


class GeneratedFileEntry(TypedDict, total=False):
    """Metadata for a generated file."""

    path: str
    content: str
    language: str
    validated: bool
    size_bytes: int


class ProviderConfigDict(TypedDict, total=False):
    """Configuration for an LLM provider."""

    name: str
    type: str
    base_url: str
    api_key: Optional[str]
    models: Dict[str, str]


class DecisionRecordDict(TypedDict, total=False):
    """A recorded agent decision for long-term memory."""

    session_id: str
    decision_type: str
    context: str
    choice: str
    reasoning: str
    outcome: str
    timestamp: str


# --------------- Protocol Definitions ---------------


@runtime_checkable
class LLMProviderProtocol(Protocol):
    """Protocol for LLM provider implementations (duck typing)."""

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        temperature: float = 0.5,
    ) -> Dict[str, Any]: ...

    async def embed(self, text: str) -> List[float]: ...

    def supports_tools(self) -> bool: ...

    def supports_vision(self) -> bool: ...


@runtime_checkable
class ModelProviderProtocol(Protocol):
    """Protocol for model provider managers (duck typing for IModelProvider)."""

    def get_client(self, role: str) -> Optional[Any]: ...

    def get_embedding_client(self) -> Optional[Any]: ...

    def get_all_clients(self) -> Dict[str, Any]: ...


@runtime_checkable
class AgentPhaseProtocol(Protocol):
    """Protocol for pipeline phase implementations (duck typing for IAgentPhase)."""

    async def execute(
        self,
        project_description: str,
        project_name: str,
        project_root: Path,
        readme_content: str,
        initial_structure: Dict[str, Any],
        generated_files: Dict[str, str],
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]: ...


@runtime_checkable
class ToolExecutorProtocol(Protocol):
    """Protocol for tool executor implementations (duck typing for IToolExecutor)."""

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> Any: ...


@runtime_checkable
class MemorySystemProtocol(Protocol):
    """Protocol for memory system implementations (duck typing for IMemorySystem)."""

    async def store_agent_memory(self, agent_id: str, key: str, data: Any) -> None: ...

    async def retrieve_agent_memory(self, agent_id: str, key: str) -> Optional[Any]: ...

    async def list_agent_memory_keys(self, agent_id: str) -> List[str]: ...

    async def clear_agent_memory(self, agent_id: str, key: Optional[str] = None) -> None: ...
