# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Ollash** (Local IT Agent) is a modular AI agent framework powered by Ollama for local IT tasks: code analysis, network diagnostics, system administration, and cybersecurity. It uses Ollama's tool-calling API to orchestrate specialized agents across domains. A secondary pipeline (Auto Agent) generates complete projects from natural language descriptions using multiple specialized LLMs.

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

# Auto Agent — generate a complete project
python auto_agent.py --description "project description" --name project_name --refine-loops 1

# Web UI (chat + project generation)
python run_web.py

# Benchmark LLM models on project generation
python auto_benchmark.py
python auto_benchmark.py --models model1 model2

# Run all tests (mocked, no Ollama needed)
pytest tests/ -v --timeout=120 --ignore=tests/test_ollama_integration.py

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

### Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `OLLASH_OLLAMA_URL` | Ollama URL for runtime (also used in Docker) | `http://localhost:11434` |
| `OLLAMA_TEST_URL` | Ollama URL for integration tests | `http://localhost:11434` |
| `OLLAMA_TEST_TIMEOUT` | Timeout for integration tests (seconds) | `300` |

## Architecture

### Entry Points

- `run_agent.py` — Interactive agent CLI → `DefaultAgent`
- `auto_agent.py` — Autonomous project generation CLI → `AutoAgent`
- `auto_benchmark.py` — LLM benchmarking CLI → `ModelBenchmarker`
- `run_web.py` — Flask web UI (chat + project generation) → `src/web/app.py`

All CLI entry points are thin wrappers that parse args and delegate to classes in `src/agents/`.

### Agent Hierarchy

`CoreAgent` (`src/agents/core_agent.py`) is the abstract base class providing shared LLM client management, logging, command execution, file validation, and event publishing. It defines `LLM_ROLES` (model name + timeout per role) and shared constants like stdlib module lists and file category patterns.

`DefaultAgent` (`src/agents/default_agent.py`, ~1000 lines) inherits from `CoreAgent` and is the interactive orchestrator:

1. **Preprocesses** the user instruction (language detection, translation, refinement)
2. **Classifies intent** to select the best LLM model (coding vs reasoning vs general)
3. Runs a **tool-calling loop** (up to 30 iterations) against Ollama until the LLM returns a final text response
4. Uses **semantic loop detection** (embedding similarity via all-minilm) to detect stuck agents and trigger a "human gate"
5. Manages **context windows** with automatic summarization at 70% token capacity

`AutoAgent` (`src/agents/auto_agent.py`) also inherits from `CoreAgent` and runs the 8-phase project generation pipeline.

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

Tool modules live in `src/utils/domains/<domain>/`. Each domain has both a tools module and a `tool_definitions.py` with Ollama function schemas. All definitions are aggregated in `src/utils/core/all_tool_definitions.py`.

`ToolRegistry` (`src/utils/core/tool_registry.py`) centralizes tool-name-to-toolset mapping and agent-type routing, extracted from `DefaultAgent` to reduce its responsibilities.

### Core Services (`src/utils/core/`)

Injected into agents via constructor:

- **OllamaClient** — HTTP client for Ollama API with retry/backoff. `chat()` returns `(response_data, usage_stats)` tuple.
- **FileManager** — File CRUD operations
- **CommandExecutor** — Shell execution with sandbox levels (`limited`/`full`)
- **GitManager** — Git operations
- **CodeAnalyzer** — Language detection, AST parsing, dependency mapping
- **MemoryManager** — Persistent conversation storage (JSON + ChromaDB reasoning cache)
- **TokenTracker** — Token usage monitoring
- **AgentLogger** — Colored console + file logging (uses colorama on Windows)
- **ToolInterface** (`ToolExecutor`) — Tool definition filtering and confirmation gates
- **PolicyManager** — Compliance and governance policies
- **LLMResponseParser** — Strips markdown fences from LLM output when models ignore raw-content instructions (`extract_raw_content()`)
- **FileValidator** — Validates generated files by extension; delegates to language-specific validators in `src/utils/core/validators/`
- **ModelRouter** — Routes prompts to specialist models, aggregates responses, uses a Senior Reviewer to select the best solution
- **EventPublisher** — Decoupled event dispatch for agent → UI communication
- **DocumentationManager** — Documentation generation utilities
- **LoopDetector** — Semantic similarity-based stuck-agent detection

Shared constants live in `src/utils/core/constants.py`; custom exception hierarchy in `src/utils/core/exceptions.py`.

### Confirmation Gates

State-modifying tools (`write_file`, `delete_file`, `git_commit`, `git_push`, etc.) require explicit user confirmation unless `--auto` mode is active. Critical paths (env files, configs, CI workflows) always force human approval regardless of mode.

### Hybrid Model Selection

Different Ollama models are selected per `config/settings.json`:
- `models.coding` — code tasks (default: `qwen3-coder-next`)
- `models.reasoning` — complex reasoning (default: `gpt-oss:20b`)
- `models.orchestration` / `models.summarization` — lightweight tasks (default: `ministral-3:8b`)
- `models.embedding` — semantic similarity (default: `all-minilm`)

## Auto Agent Pipeline

`src/agents/auto_agent.py` orchestrates an 8-phase project generation pipeline. Each phase delegates to a dedicated module in `src/utils/domains/auto_generation/`:

| Phase | Module | LLM Role |
|---|---|---|
| 1. README | `project_planner.py` | planner |
| 2. Structure | `structure_generator.py` | prototyper |
| 3. Scaffolding | (inline) | — |
| 4. Content | `file_content_generator.py` | prototyper |
| 5. Refinement | `file_refiner.py` | coder |
| 5.5. Verification | `file_completeness_checker.py` | coder |
| 6. Review | `project_reviewer.py` | generalist |
| 7. Iterative Improvement | `improvement_suggester.py` + `improvement_planner.py` | suggester + planner |
| 8. Senior Review | `senior_reviewer.py` | senior_reviewer |

LLM roles are mapped to models via `auto_agent_llms` in `config/settings.json`, with per-role timeouts in `auto_agent_timeouts`.

Key patterns in the pipeline:
- Prompts instruct models to output raw content (no markdown fences); `LLMResponseParser.extract_raw_content()` strips fences if models ignore this
- `FileValidator` validates generated files by extension; `FileCompletenessChecker` retries invalid files via LLM
- Cross-file context: content generation selects related files contextually (backend for frontend, source for deps) rather than just the last N generated
- Dependency reconciliation scans real Python imports and regenerates `requirements.txt` when hallucinated packages are detected

## Web UI (`src/web/`)

`run_web.py` launches a Flask app on port 5000 with two main features:

- **Chat** — Interactive DefaultAgent with tool-calling, streamed via SSE (`/api/chat`, `/api/chat/stream/<id>`)
- **Project Generation** — AutoAgent pipeline with live log streaming (`/api/projects/`)

Architecture uses Flask blueprints (`src/web/blueprints/`) + services (`src/web/services/`):
- `ChatEventBridge` — thread-safe `queue.Queue` bridging agent thread to SSE endpoint
- `ChatSessionManager` — manages DefaultAgent instances per session (auto_confirm=True in web mode)
- DefaultAgent accepts an optional `event_bridge` parameter to emit `tool_call`, `tool_result`, `iteration`, `final_answer`, and `error` events during `chat()`
- `middleware.py` — request-level middleware (rate limiting, etc.)

## Configuration

`config/settings.json` holds all runtime configuration: Ollama URL, model names, token limits, sandbox level, log settings, default system prompt path, `auto_agent_llms`, and `auto_agent_timeouts`.

## Testing

Tests use `pytest` with mocked Ollama calls (no live server needed). Key fixtures in `tests/conftest.py`:
- `mock_ollama_client` — patches `OllamaClient` with mock responses (uses varying embeddings to avoid loop-detector false positives)
- `temp_project_root` — creates a temp directory with config + prompt files for all agent types
- `default_agent` — fully constructed `DefaultAgent` with mocked Ollama

Integration tests requiring a live Ollama instance are in `tests/test_ollama_integration.py` (skipped in CI via `--ignore`).

CI runs on GitHub Actions (`.github/workflows/ci.yml`): lint with `ruff`, then `pytest` with `--ignore=tests/test_ollama_integration.py`. Python 3.11.

## Adding a New Tool

1. Create or extend a tool class in the appropriate `src/utils/domains/<domain>/` module
2. Register the Ollama function schema in the domain's `tool_definitions.py` and ensure it's included in `src/utils/core/all_tool_definitions.py`
3. Map the tool name to its implementation in `ToolRegistry.TOOL_MAPPING` (`src/utils/core/tool_registry.py`)
4. Add the tool name to the relevant agent type's prompt JSON in `prompts/<domain>/`
5. Ensure lazy loading is preserved — tools should only instantiate when first called
