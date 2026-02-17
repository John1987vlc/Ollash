"""Custom exception types for the Ollash agent framework.

Organized into categories:
- Infrastructure errors: External system failures (Ollama offline, disk, network)
- Agent logic errors: Internal agent reasoning failures (loops, invalid output)
- Tool errors: Tool execution failures
- Pipeline errors: AutoAgent pipeline failures
- Configuration errors: Config/prompt loading failures
- Provider errors: Multi-provider LLM failures
"""


class OllashError(Exception):
    """Base exception for all Ollash errors."""


# --------------- Infrastructure Errors ---------------


class InfrastructureError(OllashError):
    """Base exception for external infrastructure failures.

    Use this for errors caused by systems outside the agent's control:
    Ollama server, disk, network, Docker, etc.
    """


class ResourceExhaustionError(InfrastructureError):
    """Raised when a system resource is exhausted (memory, disk, GPU)."""

    def __init__(self, resource: str, message: str = ""):
        self.resource = resource
        super().__init__(
            f"Resource exhausted ({resource}): {message}" if message else f"Resource exhausted: {resource}"
        )


class SandboxUnavailableError(InfrastructureError):
    """Raised when no sandbox runtime (Docker, WASM) is available."""

    def __init__(self, attempted_runtimes: list = None):
        self.attempted_runtimes = attempted_runtimes or []
        runtimes_str = ", ".join(self.attempted_runtimes) if self.attempted_runtimes else "none"
        super().__init__(f"No sandbox runtime available (tried: {runtimes_str})")


class NetworkTimeoutError(InfrastructureError):
    """Raised when a network operation times out."""

    def __init__(self, operation: str, timeout_seconds: float):
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Network timeout after {timeout_seconds}s during: {operation}")


# --------------- Agent Logic Errors ---------------


class AgentLogicError(OllashError):
    """Base exception for agent internal reasoning failures.

    Use this for errors in the agent's own logic: stuck loops,
    malformed tool output, prompt parsing failures, etc.
    """


class InvalidToolOutputError(AgentLogicError):
    """Raised when a tool returns output that the agent cannot process."""

    def __init__(self, tool_name: str, message: str, raw_output: str = ""):
        self.tool_name = tool_name
        self.raw_output = raw_output[:500]
        super().__init__(f"Invalid output from tool '{tool_name}': {message}")


class PhaseContractViolationError(AgentLogicError):
    """Raised when a phase returns data that violates its expected contract."""

    def __init__(self, phase_name: str, violation: str):
        self.phase_name = phase_name
        self.violation = violation
        super().__init__(f"Phase '{phase_name}' contract violation: {violation}")


class PromptParsingError(AgentLogicError):
    """Raised when an LLM response cannot be parsed into the expected format."""

    def __init__(self, expected_format: str, raw_response: str = ""):
        self.expected_format = expected_format
        self.raw_response = raw_response[:500]
        super().__init__(f"Failed to parse LLM response as {expected_format}")


# --------------- Ollama / LLM Errors ---------------
# OllamaError now inherits from InfrastructureError for proper categorization
# but maintains backward compatibility as a standalone import.


class OllamaError(InfrastructureError):
    """Base exception for Ollama communication errors."""


class OllamaConnectionError(OllamaError):
    """Raised when Ollama server is unreachable."""


class OllamaModelError(OllamaError):
    """Raised when a requested model is not available."""


class OllamaRateLimitError(OllamaError):
    """Raised when the rate limiter throttles a request."""


# --------------- Agent Errors ---------------
# AgentLoopError now also inherits from AgentLogicError for categorization
# while keeping AgentError as parent for backward compatibility.


class AgentError(OllashError):
    """Base exception for agent-related errors."""


class AgentLoopError(AgentError, AgentLogicError):
    """Raised when the agent is stuck in a repetitive loop."""


class AgentTimeoutError(AgentError):
    """Raised when the agent exceeds maximum iterations."""


class AgentSwitchError(AgentError):
    """Raised when agent type switching fails (e.g., invalid agent type)."""


# --------------- Tool Errors ---------------


class ToolError(OllashError):
    """Base exception for tool execution errors."""


class ToolNotFoundError(ToolError):
    """Raised when a requested tool doesn't exist."""


class ToolExecutionError(ToolError):
    """Raised when a tool execution fails."""

    def __init__(self, tool_name: str, message: str, original_error: Exception = None):
        self.tool_name = tool_name
        self.original_error = original_error
        super().__init__(f"Tool '{tool_name}' failed: {message}")


class ToolPermissionError(ToolError):
    """Raised when a tool requires confirmation that wasn't granted."""


# --------------- Pipeline Errors ---------------


class PipelineError(OllashError):
    """Base exception for auto-generation pipeline errors."""


class PipelinePhaseError(PipelineError):
    """Raised when a specific pipeline phase fails."""

    def __init__(self, phase_name: str, message: str):
        self.phase_name = phase_name
        super().__init__(f"Phase '{phase_name}' failed: {message}")


class FileValidationError(PipelineError):
    """Raised when a generated file fails validation."""


class StructureGenerationError(PipelineError):
    """Raised when project structure generation fails."""


class ParallelPhaseError(PipelineError):
    """Raised when one or more phases fail during parallel execution."""

    def __init__(self, failed_phases: dict):
        self.failed_phases = failed_phases
        phase_names = ", ".join(failed_phases.keys())
        super().__init__(f"Parallel execution failed in phases: {phase_names}")


# --------------- Configuration Errors ---------------


class ConfigurationError(OllashError):
    """Raised for configuration-related issues."""


class PromptLoadError(ConfigurationError):
    """Raised when a prompt file cannot be loaded or is invalid."""


# --------------- Provider Errors ---------------


class ProviderError(OllashError):
    """Base exception for LLM provider errors (multi-provider support)."""


class ProviderConnectionError(ProviderError):
    """Raised when an LLM provider is unreachable."""

    def __init__(self, provider_name: str, message: str = ""):
        self.provider_name = provider_name
        super().__init__(f"Provider '{provider_name}' connection failed: {message}")


class ProviderAuthenticationError(ProviderError):
    """Raised when authentication with an LLM provider fails."""

    def __init__(self, provider_name: str):
        self.provider_name = provider_name
        super().__init__(f"Authentication failed for provider '{provider_name}'")
