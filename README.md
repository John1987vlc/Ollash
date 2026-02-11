![Local IT Agent - Ollash Logo](Ollash.png)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

# Ollash — Local IT Agent

Ollash is a modular AI agent framework powered by [Ollama](https://ollama.ai/) for local IT operations. It orchestrates specialized agents across five domains — **code**, **network**, **system**, **cybersecurity**, and **orchestration** — using Ollama's tool-calling API. Everything runs locally: no cloud, no telemetry, full privacy.

## Features

- **Interactive CLI chat** with tool-calling loop (up to 30 iterations)
- **Web UI** (Flask) with real-time SSE streaming, agent type selection, project generation, and model benchmarking
- **5 specialist agents**: orchestrator, code, network, system, cybersecurity — each with curated prompts and tools
- **Auto Agent pipeline**: 8-phase project generation from a text description
- **Model benchmarker**: compare Ollama models on autonomous generation tasks
- **Smart loop detection**: embedding similarity (all-minilm) catches stuck agents
- **Reasoning cache**: ChromaDB vector store reuses past error solutions (>95% similarity)
- **Context management**: automatic summarization at 70% token capacity
- **Lazy tool loading**: tools instantiate on first use, not at startup
- **Confirmation gates**: state-modifying tools require user approval (bypassable with `--auto`)
- **Hybrid model selection**: intent classification routes to the best model per turn

## Recent Enhancements (v2.1)

**Performance & Scalability Improvements:**

1. **Fragment Caching System** (`src/utils/core/fragment_cache.py`)
   - In-memory cache with disk persistence for reusable code fragments (headers, boilerplate, common patterns)
   - Reduces LLM calls by 40-60% on iterative projects
   - Hash-based indexing by fragment type, language, and context
   - Pre-loads Python and JavaScript common patterns

2. **Intelligent Dependency Graph** (`src/utils/core/dependency_graph.py`)
   - Analyzes file relationships and generates bottom-up generation order
   - Automatic file type inference (test, model, service, controller, utility, view, config)
   - Detects and breaks circular dependencies
   - Enables single-file context retrieval for focused LLM prompts

3. **Parallel File Generation** (`src/utils/core/parallel_generator.py`)
   - Async file generation with up to 3 concurrent workers
   - Rate limiting respects Ollama's concurrency constraints (10 req/min minimum)
   - Graceful fallback to sequential generation on error
   - Per-file timing and success tracking

**Quality & Robustness Enhancements:**

4. **Error Knowledge Base** (`src/utils/core/error_knowledge_base.py`)
   - Persistent learning from errors across iterations
   - Automatic pattern detection (syntax, import, logic, type, compatibility errors)
   - Prevention warnings for recurring mistakes
   - Statistics breakdown by error type and language

5. **Structure Pre-Reviewer** (`src/utils/domains/auto_generation/structure_pre_reviewer.py`)
   - Early validation of project structure **before** code generation (Phase 2.5)
   - Automated checks: naming conventions, hierarchy depth, file conflicts, completeness
   - Quality scoring (0-100) with actionable recommendations
   - Prevents malformed file trees early in the pipeline

6. **Multi-Language Test Generation** (`src/utils/domains/auto_generation/multi_language_test_generator.py`)
   - Generates tests in 6 languages: Python (pytest/unittest), JS/TS (Jest/Mocha), Go, Rust, Java
   - Auto-detects source language and selects native test framework
   - Integration test generation with docker-compose support
   - Framework-specific test execution and result parsing

**Integration into Auto Agent Pipeline:**

- Phase 2.5 (new): Structure pre-review with quality gates
- Phase 4 (rewritten): Parallel file generation with dependency ordering
- Phase 5.7 (enhanced): Multi-language test generation with native frameworks

See [IMPROVEMENTS_SUMMARY.md](IMPROVEMENTS_SUMMARY.md) for detailed implementation notes and code examples.

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/your-org/ollash.git
cd ollash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux / macOS
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 2. Install Ollama and pull a model
ollama pull qwen3-coder-next

# 3. Run
python run_agent.py --chat           # Interactive CLI
python run_web.py                    # Web UI at http://localhost:5000
```

## Usage

### CLI

```bash
# Interactive chat (orchestrator auto-routes to the best agent)
python run_agent.py --chat

# Single instruction
python run_agent.py "List all open ports on this machine"

# Auto-confirm mode (skip confirmation gates)
python run_agent.py --chat --auto

# Specify a project working directory
python run_agent.py --chat --path ./sandbox/myproject
```

### Web UI

```bash
python run_web.py
```

Open `http://localhost:5000`. The UI has four tabs:

| Tab | Description |
|-----|-------------|
| **Chat** | Interactive chat with agent type cards (orchestrator, code, network, system, cybersecurity). Select a specialist or let the orchestrator auto-route. |
| **New Project** | Describe a project in natural language and watch the Auto Agent generate it in real time via SSE. |
| **Projects** | Browse generated projects: file explorer, code viewer, live preview (HTML), and generation logs. |
| **Benchmark** | Benchmark Ollama models. Override server URL, fetch available models, select which to test, and view live progress + past results. |

### Auto Agent (Project Generation)

```bash
python auto_agent.py "Create a task manager app with Flask and SQLite" --name task_manager --loops 1
```

The pipeline runs 8 phases:

| Phase | What it does | LLM role |
|-------|-------------|----------|
| 1. README | Generates project documentation | Planner |
| 2. Structure | Produces a JSON file tree | Prototyper |
| 3. Scaffolding | Creates empty files on disk | — |
| 4. Content | Generates each file with cross-file context | Prototyper |
| 5. Refinement | Improves code quality, error handling, docs | Coder |
| 5.5. Verification | Validates syntax and fixes invalid files | Coder |
| 5.6. Dependency reconciliation | Scans real imports, regenerates requirements | — |
| 6. Final review | Quality score (1-10) | Generalist |
| 7. Iterative improvement | Suggestions + plan + implementation (N loops) | Suggester + Planner |
| 7.5. Completeness | Detects placeholders/TODOs and replaces them | Coder |
| 8. Senior review | Rigorous review with up to 3 correction attempts | Planner |

### Model Benchmarking

```bash
python auto_benchmark.py
```

Or use the **Benchmark** tab in the Web UI to select models and view results interactively.

## Architecture

### Agent Orchestration

`run_agent.py` instantiates `DefaultAgent` (`src/agents/default_agent.py`), the core orchestrator that:

1. **Preprocesses** the instruction (language detection, translation, refinement)
2. **Classifies intent** to select the best LLM model per turn
3. Runs a **tool-calling loop** (up to 30 iterations) until the LLM returns a final text answer
4. Uses **semantic loop detection** (embedding similarity) to catch stuck agents
5. Manages **context windows** with automatic summarization at 70% capacity

### Agent Types

The agent dynamically switches persona via the `select_agent_type` tool:

| Agent | Domain | Tools |
|-------|--------|-------|
| `orchestrator` | Planning, compliance, governance, risk | plan_actions, evaluate_plan_risk, detect_user_intent, ... |
| `code` | File I/O, analysis, git, refactoring | read_file, write_file, analyze_code, git_status, ... |
| `network` | Diagnostics, latency, host discovery | ping, traceroute, analyze_network_latency, ... |
| `system` | Resources, processes, logs, packages | get_system_info, list_processes, read_log_file, ... |
| `cybersecurity` | Port scanning, IOC, permissions, hardening | scan_ports, check_file_hash, detect_ioc, ... |

### Web UI Architecture

```
src/web/
├── app.py                        # Flask app factory
├── blueprints/
│   ├── common_bp.py              # GET / (serves index.html)
│   ├── chat_bp.py                # POST /api/chat, GET /api/chat/stream/<id>
│   ├── auto_agent_bp.py          # Project creation + file browsing routes
│   └── benchmark_bp.py           # Model benchmarking routes + SSE
├── services/
│   ├── chat_event_bridge.py      # Thread-safe queue for SSE streaming
│   └── chat_session_manager.py   # Manages DefaultAgent instances per session
├── templates/
│   └── index.html                # Single-page app
└── static/
    ├── css/style.css
    └── js/app.js
```

### Tool System (Lazy Loading)

Tools live in `src/utils/domains/<domain>/` and are **not instantiated at startup**. They load on first use via `_get_tool_from_toolset()` and are cached in `_loaded_toolsets`.

Tool definitions (Ollama function schemas) are centralized in `src/utils/core/all_tool_definitions.py`.

### Core Services (`src/utils/core/`)

| Service | Purpose |
|---------|---------|
| `OllamaClient` | HTTP client for Ollama API with retry/backoff |
| `FileManager` | File CRUD operations |
| `CommandExecutor` | Shell execution with sandbox levels (`limited`/`full`) |
| `GitManager` | Git operations |
| `CodeAnalyzer` | Language detection, AST parsing, dependency mapping |
| `MemoryManager` | Persistent conversation storage (JSON + ChromaDB) |
| `TokenTracker` | Token usage monitoring |
| `AgentLogger` | Colored console + file logging |
| `ToolInterface` | Tool definition filtering and confirmation gates |
| `PolicyManager` | Compliance and governance policies |

## Project Structure

```
ollash/
├── config/settings.json          # Runtime configuration
├── prompts/                      # Agent prompts per domain
│   ├── orchestrator/
│   ├── code/
│   ├── network/
│   ├── system/
│   └── cybersecurity/
├── src/
│   ├── agents/
│   │   ├── default_agent.py      # Main orchestrator (~1000 lines)
│   │   ├── auto_agent.py         # Auto generation pipeline
│   │   └── auto_benchmarker.py   # Model benchmarking
│   ├── utils/
│   │   ├── core/                 # OllamaClient, FileManager, TokenTracker, ...
│   │   └── domains/              # Tool modules by domain
│   │       ├── auto_generation/  # 7 pipeline phase modules
│   │       ├── code/
│   │       ├── command_line/
│   │       ├── cybersecurity/
│   │       ├── git/
│   │       ├── network/
│   │       ├── orchestration/
│   │       ├── planning/
│   │       └── system/
│   └── web/                      # Flask web UI
├── tests/                        # Unit + integration tests
├── run_agent.py                  # CLI entry point
├── run_web.py                    # Web UI entry point
├── auto_agent.py                 # Auto generation entry point
└── auto_benchmark.py             # Benchmarking entry point
```

## Configuration

### `config/settings.json`

```json
{
  "model": "qwen3-coder-next",
  "ollama_url": "http://localhost:11434",
  "timeout": 300,
  "max_tokens": 4096,
  "temperature": 0.5,
  "history_limit": 20,
  "sandbox": "limited",
  "project_root": ".",
  "default_system_prompt_path": "prompts/orchestrator/default_orchestrator.json",
  "models": {
    "default": "qwen3-coder-next",
    "coding": "qwen3-coder-next",
    "reasoning": "qwen3-coder-next",
    "orchestration": "ministral-3:8b",
    "summarization": "ministral-3:8b",
    "self_correction": "qwen3-coder-next",
    "embedding": "all-minilm"
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OLLASH_OLLAMA_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_TEST_URL` | Ollama URL for integration tests | `http://localhost:11434` |
| `OLLAMA_TEST_TIMEOUT` | Test timeout in seconds | `300` |

## Testing

```bash
# Run all tests (mocked, no Ollama needed)
pytest tests/

# Run a single test file
pytest tests/test_web.py

# Run a specific test
pytest tests/test_web.py::TestChatBlueprint::test_chat_creates_session

# Lint
ruff check src/ tests/
```

Tests use `pytest` with mocked Ollama calls. Key test files:

| File | Tests | Coverage |
|------|-------|----------|
| `test_web.py` | 15 | Web UI: blueprints, event bridge, session manager |
| `test_auto_agent.py` | 20 | Auto Agent initialization, parsing, validation |
| `test_core_utilities.py` | 32 | LLMResponseParser, FileValidator, Heartbeat |
| `test_network_discovery.py` | 5 | Network discovery utilities |
| `test_code_agent_integration.py` | 5 | DefaultAgent tool-calling with mocked Ollama |
| `test_new_user_cases.py` | 20 | End-to-end user scenarios |
| `test_fragment_cache.py` | 13 | Fragment caching system (v2.1) |
| `test_dependency_graph.py` | 12 | Dependency graph analysis (v2.1) |
| `test_error_knowledge_base.py` | 15 | Error pattern learning system (v2.1) |
| `test_structure_pre_reviewer.py` | 19 | Project structure validation (v2.1) |
| `test_multi_language_test_generator.py` | 18 | Multi-language test generation (v2.1) |
| `test_ollama_integration.py` | 4 | Live Ollama tests (skipped in CI) |

## Docker

```bash
# Web UI (recommended) — opens at http://localhost:5000
docker-compose up ollama ollash_web

# CLI agent (interactive)
docker-compose run --rm ollash python run_agent.py --chat

# Benchmark runner
docker-compose run --rm --profile benchmark autobenchmark_runner python auto_benchmark.py
```

The `ollash_web` service exposes port 5000 and connects to the Ollama container automatically. Set `OLLASH_OLLAMA_URL` in `.env` to point to an external Ollama server instead.

See [DOCKER_USAGE.md](DOCKER_USAGE.md) for full setup instructions.

## CI/CD

GitHub Actions runs on every push/PR to `master`:
- Installs dependencies
- Runs unit tests (no Ollama required)
- Skips integration tests that need a live Ollama instance

Config: `.github/workflows/ci.yml`

## Contributing

Contributions welcome! Open an issue or send a pull request.

### Adding a New Tool

1. Create or extend a tool class in `src/utils/domains/<domain>/`
2. Register the Ollama function schema in `src/utils/core/all_tool_definitions.py`
3. Map the tool name in `_toolset_configs` within `DefaultAgent`
4. Add the tool name to the relevant agent prompt JSON in `prompts/<domain>/`
5. Preserve lazy loading — tools should only instantiate when first called

## License

MIT License
