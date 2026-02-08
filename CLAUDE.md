# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Ollash** (Local IT Agent) is a modular AI agent framework powered by Ollama for local IT tasks: code analysis, network diagnostics, system administration, and cybersecurity. It uses Ollama's tool-calling API to orchestrate specialized agents across domains.

## Commands

```bash
# Run interactive chat
python run_agent.py --chat

# Run single instruction
python run_agent.py "your instruction here"

# Auto-confirm mode (skip confirmation gates)
python run_agent.py --chat --auto

# Specify project path
python run_agent.py --chat --path ./sandbox/myproject

# Run all tests (mocked, no Ollama needed)
pytest tests/

# Run a single test file
pytest tests/test_code_agent_integration.py

# Run a specific test
pytest tests/test_code_agent_integration.py::TestClassName::test_method_name

# Lint
ruff check src/ tests/

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

**PYTHONPATH**: Must include the project root for imports to work. CI sets this via `GITHUB_ENV`; locally, run from the project root or set it manually.

## Architecture

### Agent Orchestration

The single entry point is `run_agent.py`, which instantiates `DefaultAgent` (in `src/agents/default_agent.py`). This is the core orchestrator (~1000 lines) that:

1. **Preprocesses** the user instruction (language detection, translation, refinement)
2. **Classifies intent** to select the best LLM model (coding vs reasoning vs general)
3. Runs a **tool-calling loop** (up to 30 iterations) against Ollama until the LLM returns a final text response (no more tool calls)
4. Uses **semantic loop detection** (embedding similarity via all-minilm) to detect stuck agents and trigger a "human gate"
5. Manages **context windows** with automatic summarization at 70% token capacity

### Agent Types & Tool Routing

The agent dynamically switches persona via `select_agent_type` tool. Each type loads a curated prompt + tool subset from `prompts/<domain>/`:

| Agent Type | Domain | Prompt File |
|---|---|---|
| `orchestrator` | Planning, compliance, governance | `prompts/orchestrator/default_orchestrator.json` |
| `code` | File I/O, analysis, git, refactoring | `prompts/code/default_agent.json` |
| `network` | Diagnostics, latency, discovery | `prompts/network/default_network_agent.json` |
| `system` | Resources, processes, logs | `prompts/system/default_system_agent.json` |
| `cybersecurity` | Scanning, permissions, IOC | `prompts/cybersecurity/default_cybersecurity_agent.json` |

### Tool System (Lazy Loading)

Tools are **not instantiated at startup**. They are lazy-loaded on first use via `_get_tool_from_toolset()` and cached in `_loaded_toolsets`. This is a key architectural decision — respect it when adding tools.

**Tool modules live in `src/utils/domains/<domain>/`**:
- `code/` — file_system_tools, code_analysis_tools, advanced_code_tools
- `command_line/` — command_line_tools
- `git/` — git_operations_tools
- `planning/` — planning_tools
- `orchestration/` — orchestration_tools
- `network/` — network_tools, advanced_network_tools
- `system/` — system_tools, advanced_system_tools
- `cybersecurity/` — cybersecurity_tools, advanced_cybersecurity_tools
- `bonus/` — bonus_tools

**Tool definitions** (Ollama function schemas) are centralized in `src/utils/core/all_tool_definitions.py`.

### Core Services (`src/utils/core/`)

These are injected into `DefaultAgent` at construction:

- **OllamaClient** — HTTP client for Ollama API with retry/backoff
- **FileManager** — File CRUD operations
- **CommandExecutor** — Shell execution with sandbox levels (`limited`/`full`)
- **GitManager** — Git operations
- **CodeAnalyzer** — Language detection, AST parsing, dependency mapping
- **MemoryManager** — Persistent conversation storage (JSON + ChromaDB reasoning cache)
- **TokenTracker** — Token usage monitoring
- **AgentLogger** — Colored console + file logging
- **ToolInterface** — Tool definition filtering and confirmation gates
- **PolicyManager** — Compliance and governance policies

### Confirmation Gates

State-modifying tools (`write_file`, `delete_file`, `git_commit`, `git_push`, etc.) require explicit user confirmation unless `--auto` mode is active. Critical paths (env files, configs, CI workflows) always force human approval regardless of mode.

### Hybrid Model Selection

Different Ollama models are selected based on intent classification:
- **Coding**: `qwen3-coder-next` (configured as `code-model`)
- **Orchestration/Summarization**: `ministral-3:8b`
- Models are configured in `config/settings.json`

## Configuration

`config/settings.json` holds runtime configuration: Ollama URL, model names, token limits, sandbox level, log settings, and the default system prompt path.

## Testing

Tests use `pytest` with mocked Ollama calls (no live server needed). Key fixtures in `tests/conftest.py`:
- `mock_ollama_client` — patches `OllamaClient` with mock responses
- `temp_project_root` — creates a temp directory with config + prompt files
- `default_agent` — fully constructed `DefaultAgent` with mocked Ollama

Integration tests that require a live Ollama instance are in `tests/test_ollama_integration.py` (skipped in CI).

## Adding a New Tool

1. Create or extend a tool class in the appropriate `src/utils/domains/<domain>/` module
2. Register the Ollama function schema in `src/utils/core/all_tool_definitions.py`
3. Map the tool name to its implementation in `_toolset_configs` within `DefaultAgent`
4. Add the tool name to the relevant agent type's prompt JSON in `prompts/<domain>/`
5. Ensure lazy loading is preserved — tools should only instantiate when first called
