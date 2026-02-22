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

All configuration is now managed via environment variables, loaded from a `.env` file at the project root. Copy `.env.example` to `.env` to get started.

| Variable | Purpose | Default |
|---|---|---|
| `OLLAMA_URL` | Ollama URL for runtime (also used in Docker) | `http://localhost:11434` |
| `DEFAULT_MODEL` | The default model for general tasks. | `ministral-3:8b` |
| `*_JSON` | Many variables contain full JSON configurations. See `.env.example` for details. | |
| `OLLAMA_TEST_URL` | Ollama URL for integration tests | `http://localhost:11434` |
| `OLLAMA_TEST_TIMEOUT`| Timeout for integration tests (seconds) | `300` |


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

- **`config.py`**: Centralized configuration loader. It reads the `.env` file at startup and provides a `config` object used throughout the application.
- **OllamaClient**: HTTP client for Ollama API with retry/backoff.
- **FileManager**: File CRUD operations
- **CommandExecutor**: Shell execution with sandbox levels.
- **... and other services as before.**

### Confirmation Gates

State-modifying tools (`write_file`, `delete_file`, `git_commit`, etc.) require explicit user confirmation unless `--auto` mode is active. Critical paths (env files, CI workflows) always force human approval regardless of mode.

### Hybrid Model Selection

Different Ollama models are selected based on the `LLM_MODELS_JSON` environment variable in the `.env` file. This JSON object maps roles to specific model names:
- `models.coding` — code tasks (default: `qwen3-coder:30b`)
- `models.reasoning` — complex reasoning (default: `gpt-oss:20b`)
- `models.orchestration` / `models.summarization` — lightweight tasks (default: `ministral-3:8b`)
- `models.embedding` — semantic similarity (default: `all-minilm`)

## Auto Agent Pipeline

`src/agents/auto_agent.py` orchestrates an 8-phase project generation pipeline. Each phase delegates to a dedicated module in `src/utils/domains/auto_generation/`.

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

LLM roles are mapped to models via the `LLM_MODELS_JSON` environment variable, which also defines per-role timeouts.

Key patterns in the pipeline:
- Prompts instruct models to output raw content; `LLMResponseParser` strips markdown fences if models ignore this.
- `FileValidator` and `FileCompletenessChecker` ensure code quality and retry generation on failure.
- Cross-file context is used for generation, and dependency reconciliation fixes hallucinated packages.

## Web UI (`src/web/`)

`run_web.py` launches a Flask app on port 5000. `src/web/app.py` is the app factory, which now injects the centralized configuration into the app context, making it available to all blueprints.

- **Chat** — Interactive DefaultAgent streamed via SSE.
- **Project Generation** — AutoAgent pipeline with live log streaming.

## Configuration

All runtime configuration is managed via environment variables loaded from a `.env` file in the project root. The `.env.example` file serves as a template for all required variables. The core loading logic is handled by `src/core/config.py`.

## Testing

Tests use `pytest` with mocked Ollama calls. Key fixtures in `tests/conftest.py`:
- `mock_ollama_client`
- `temp_project_root`
- `default_agent`

Integration tests requiring a live Ollama instance are in `tests/test_ollama_integration.py` (skipped in CI).

CI runs on GitHub Actions (`.github/workflows/ci.yml`).

## Adding a New Tool

1. Create or extend a tool class in `src/utils/domains/<domain>/`.
2. Register the Ollama function schema in the domain's `tool_definitions.py`.
3. Map the tool name in `ToolRegistry.TOOL_MAPPING` (`src/utils/core/tool_registry.py`).
4. Add the tool name to the relevant agent type's prompt JSON in `prompts/`.
5. Ensure lazy loading is preserved.
