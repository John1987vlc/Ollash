"""Centralized constants for the Ollash agent framework.

Extracted from various modules to avoid magic numbers and enable configuration.
"""

# --------------- Agent Constants ---------------

MAX_INSTRUCTION_LENGTH = 10000
MAX_ITERATIONS = 30
CONTEXT_SUMMARIZATION_THRESHOLD = 0.7  # Summarize at 70% token capacity

# Loop detection
LOOP_DETECTION_THRESHOLD = 3
LOOP_SIMILARITY_THRESHOLD = 0.95
STAGNATION_TIMEOUT_MINUTES = 2

# --------------- Auto-Agent Pipeline Constants ---------------

# File generation
MAX_RETRIES_PER_FILE = 2
MAX_RELATED_FILES = 8
README_TRUNCATION_SHORT = 500
README_TRUNCATION_LONG = 1000

# Review
MAX_REVIEW_ATTEMPTS = 3
MAX_REQUIREMENTS_LINES = 30

# Default models (fallbacks when config doesn't specify)
DEFAULT_PROTOTYPER_MODEL = "gpt-oss:20b"
DEFAULT_CODER_MODEL = "qwen3-coder:30b"
DEFAULT_PLANNER_MODEL = "gpt-oss:20b"
DEFAULT_GENERALIST_MODEL = "gpt-oss:20b"
DEFAULT_SUGGESTER_MODEL = "gpt-oss:20b"
DEFAULT_EMBEDDING_MODEL = "all-minilm"
DEFAULT_ORCHESTRATION_MODEL = "ministral-3:8b"

# Default timeouts per role (seconds)
DEFAULT_PROTOTYPER_TIMEOUT = 600
DEFAULT_CODER_TIMEOUT = 480
DEFAULT_PLANNER_TIMEOUT = 480
DEFAULT_GENERALIST_TIMEOUT = 300
DEFAULT_SUGGESTER_TIMEOUT = 300

# --------------- Web UI Constants ---------------

MAX_CHAT_SESSIONS = 5
DEFAULT_WEB_HOST = "0.0.0.0"
DEFAULT_WEB_PORT = 5000
STATUS_CHECK_INTERVAL_MS = 30000
MESSAGE_TIMEOUT_MS = 5000

# Rate limiting defaults
RATE_LIMIT_API_MAX = 60  # requests per window
RATE_LIMIT_CHAT_MAX = 20
RATE_LIMIT_BENCHMARK_MAX = 5
RATE_LIMIT_WINDOW_SECONDS = 60

# --------------- Tool Constants ---------------

# Common port list for cybersecurity scanning
COMMON_SCAN_PORTS = "21,22,23,25,53,80,110,143,443,3389,8080"

# State-modifying tools that require confirmation
STATE_MODIFYING_TOOLS = [
    "write_file",
    "delete_file",
    "run_command",
    "install_package",
]

# --------------- Embedding Cache Constants ---------------

EMBEDDING_CACHE_MAX_SIZE = 10000
EMBEDDING_CACHE_TTL_SECONDS = 3600

# --------------- GPU-Aware Rate Limiter Constants ---------------

GPU_RATE_LIMITER_DEGRADATION_THRESHOLD_MS = 5000.0
GPU_RATE_LIMITER_RECOVERY_THRESHOLD_MS = 2000.0
GPU_RATE_LIMITER_MIN_RPM = 5
GPU_RATE_LIMITER_EMA_ALPHA = 0.3

# --------------- Model Health Constants ---------------

MODEL_HEALTH_FAILURE_THRESHOLD = 3
MODEL_HEALTH_WINDOW_SIZE = 20

# --------------- Async Tool Execution Constants ---------------

ASYNC_TOOL_MAX_WORKERS = 3

# --------------- Ollama Constants ---------------

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_TIMEOUT = 300
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.5
