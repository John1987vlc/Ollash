"""Custom exception types for the Ollash agent framework."""


class OllashError(Exception):
    """Base exception for all Ollash errors."""


# --------------- Agent Errors ---------------

class AgentError(OllashError):
    """Base exception for agent-related errors."""


class AgentLoopError(AgentError):
    """Raised when the agent is stuck in a repetitive loop."""


class AgentTimeoutError(AgentError):
    """Raised when the agent exceeds maximum iterations."""


class AgentSwitchError(AgentError):
    """Raised when agent type switching fails (e.g., invalid agent type)."""


# --------------- Ollama / LLM Errors ---------------

class OllamaError(OllashError):
    """Base exception for Ollama communication errors."""


class OllamaConnectionError(OllamaError):
    """Raised when Ollama server is unreachable."""


class OllamaModelError(OllamaError):
    """Raised when a requested model is not available."""


class OllamaRateLimitError(OllamaError):
    """Raised when the rate limiter throttles a request."""


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


# --------------- Configuration Errors ---------------

class ConfigurationError(OllashError):
    """Raised for configuration-related issues."""


class PromptLoadError(ConfigurationError):
    """Raised when a prompt file cannot be loaded or is invalid."""
