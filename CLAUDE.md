# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Ollash** is a modular AI agent framework powered by Ollama for local IT tasks: code analysis, network diagnostics, system administration, and cybersecurity. It uses Ollama's tool-calling API to orchestrate specialized agents across domains. A secondary pipeline (AutoAgent) generates complete projects from natural language descriptions using multiple specialized LLMs.

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

# Auto Agent — generate a complete project from description
python auto_agent.py --description "project description" --name project_name

# Web UI (chat + project generation at http://localhost:5000)
python run_web.py

# Benchmark LLM models on project generation
python auto_benchmark.py
python auto_benchmark.py --models model1 model2

# Run all tests (mocked Ollama, no live server needed)
pytest tests/ -v --timeout=120 --ignore=tests/test_ollama_integration.py

# Run a single test file
pytest tests/test_code_agent_integration.py

# Run a specific test
pytest tests/test_code_agent_integration.py::TestClassName::test_method_name

# Lint
ruff check backend/ frontend/ tests/

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

**PYTHONPATH**: Must include the project root. Run from project root or set manually.

## Architecture

### Directory Structure

- `backend/` — All Python backend code
  - `agents/` — Agent implementations (CoreAgent, DefaultAgent, AutoAgent)
  - `core/` — Kernel, config, DI containers
  - `services/` — Shared services (LLMClientManager)
  - `interfaces/` — Abstract interfaces
  - `utils/core/` — Core utilities (FileManager, CommandExecutor, etc.)
  - `utils/domains/` — Domain-specific tools by category (code, network, system, cybersecurity)
- `frontend/` — Flask web application (app.py, blueprints/, services/)
- `prompts/` — JSON prompt templates per agent type
- `tests/` — Unit and integration tests

### Entry Points

- `run_agent.py` → `DefaultAgent` (interactive CLI)
- `auto_agent.py` → `AutoAgent` (project generation)
- `auto_benchmark.py` → Model benchmarking
- `run_web.py` → Flask web UI

### Agent Hierarchy

`CoreAgent` (`backend/agents/core_agent.py`) is the abstract base providing:
- LLM client management via injected `LLMClientManager`
- Logging via `AgentLogger`, command execution via `CommandExecutor`
- Token tracking, file validation, event publishing

`DefaultAgent` (`backend/agents/default_agent.py`) is the interactive orchestrator:
1. Preprocesses user instruction (language detection, translation)
2. Classifies intent → selects specialist model
3. Runs tool-calling loop (up to 30 iterations) against Ollama
4. Uses semantic loop detection (embedding similarity) to detect stuck agents

`AutoAgent` (`backend/agents/auto_agent.py`) runs the multi-phase project generation pipeline.

### Dependency Injection

Services are wired via `dependency-injector` in `backend/core/containers.py`. The `main_container` provides factories for all agents and phases. Entry points call `main_container.wire()` to activate DI.

### Tool System

Tools are **lazy-loaded** on first use via `_get_tool_from_toolset()` and cached. Never instantiate tools in constructors.

- Tool modules: `backend/utils/domains/<domain>/` (code, network, system, cybersecurity, orchestration, planning, multimedia, auto_generation)
- Each domain has a `tool_definitions.py` with Ollama function schemas
- `ToolRegistry` (`backend/utils/core/tool_registry.py`) maps tool names to implementations
- Tools are discovered dynamically via `@ollash_tool` decorator

### Agent Types & Prompts

Agent type is selected dynamically via `select_agent_type` tool. Each loads a curated prompt from `prompts/<domain>/`:

| Type | Prompt File |
|------|-------------|
| orchestrator | `prompts/orchestrator/default_orchestrator.json` |
| code | `prompts/code/default_agent.json` |
| network | `prompts/network/default_network_agent.json` |
| system | `prompts/system/default_system_agent.json` |
| cybersecurity | `prompts/cybersecurity/default_cybersecurity_agent.json` |

### AutoAgent Phases

Phases live in `backend/agents/auto_agent_phases/`. Key phases:
- `readme_generation_phase` → README creation
- `structure_generation_phase` → Directory structure
- `file_content_generation_phase` → File content
- `test_generation_execution_phase` → Test generation
- `senior_review_phase` → Final review

Each phase receives a `PhaseContext` with shared services and project state.

### Core Services

Located in `backend/utils/core/`:
- `FileManager` — File CRUD with validation
- `CommandExecutor` — Shell execution with sandbox levels
- `FileValidator` — Validates generated files by extension
- `EventPublisher` — Decoupled event dispatch (agent → web UI)
- `RAGContextSelector` — Contextual file selection for generation

### Configuration

Configuration loaded from `.env` file via `ConfigLoader` (`backend/core/config_loader.py`). Key variables:

| Variable | Purpose |
|----------|---------|
| `OLLAMA_URL` | Ollama server URL |
| `LLM_MODELS_JSON` | Model names and timeouts per role (planner, coder, reviewer, etc.) |
| `TOOL_SETTINGS_JSON` | Sandbox level, rate limits, iteration limits |

`AgentKernel` (`backend/core/kernel.py`) provides access to validated config schemas.

### Confirmation Gates

State-modifying tools (`write_file`, `delete_file`, `git_commit`, `run_command`) require explicit user confirmation unless `--auto` mode. Critical paths (env files, CI workflows) always require approval.

## Testing

Tests use `pytest` with mocked Ollama. Fixtures in `tests/conftest.py`:
- `temp_project_root` — Creates temp directory with config + prompt files
- `default_agent` — Fully constructed DefaultAgent with mocked Ollama

Integration tests requiring live Ollama are in `tests/test_ollama_integration.py` (skipped in CI).

Test markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`

## Adding a New Tool

1. Create/extend tool class in `backend/utils/domains/<domain>/`
2. Register schema in domain's `tool_definitions.py`
3. Add `@ollash_tool` decorator for auto-discovery
4. Add tool name to relevant agent type's prompt JSON in `prompts/`
5. Preserve lazy loading — do not instantiate in agent constructors

## Code Style

- Python 3.8+ (CI tests with 3.11)
- Async patterns for I/O operations
- Type hints with Pydantic v2 for config validation
- Logging via `AgentLogger` — never use raw `print()` for operational output
- File operations via `FileManager`, shell commands via `CommandExecutor`