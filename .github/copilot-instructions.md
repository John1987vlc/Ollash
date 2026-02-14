# Ollash — Agent Workspace Instructions

Ollash is a modular AI agent framework powered by Ollama for autonomous task execution: code generation, IT diagnostics, and project scaffolding. This document guides AI agents through its architecture and conventions.

## Code Style

- **Python 3.8+** (verified in CI with 3.11)
- **Async patterns**: Use `asyncio` for I/O; agents prefer `async` implementations
- **Service injection**: Core services (OllamaClient, FileManager, CommandExecutor) are injected into agents at construction, never instantiated directly
- **Lazy tool loading**: Tools are instantiated only on first use via `_get_tool_from_toolset()` and cached in `_loaded_toolsets`—preserve this pattern when adding tools
- **Type hints**: Use `from typing import ...` annotations; Pydantic v2.12+ for config validation
- **Logging**: Use `AgentLogger` (colorama on Windows); never use raw `print()` for operational output
- **File operations**: Delegate to `FileManager` service; validate generated files via `FileValidator` by extension

Key style examples: [CoreAgent](src/agents/core_agent.py), [DefaultAgent](src/agents/default_agent.py)

## Architecture

### Agent Hierarchy

All agents inherit from [CoreAgent](src/agents/core_agent.py) which provides:
- Shared LLM client management (OllamaClient singleton per Ollama URL)
- Logging, command execution, file I/O
- Token tracking and context window management (summarize at 70% capacity)
- Semantic loop detection (embedding similarity via `all-minilm`; max 30 iterations)

**[DefaultAgent](src/agents/default_agent.py)** (~1000 lines) is the interactive orchestrator:
1. Preprocess user instruction (language detection, translation)
2. Classify intent → select specialist LLM model (coding/reasoning/general)
3. Execute tool-calling loop against Ollama until LLM returns final text
4. Emit events (`tool_call`, `tool_result`, `iteration`, `final_answer`, `error`) for UI consumption

**[AutoAgent](src/agents/auto_agent.py)** runs an 8-phase project generation pipeline (README → Structure → Scaffolding → Content → Refinement → Verification → Review → Senior Review).

### Tool System

Tools live in `src/utils/domains/<domain>/` (e.g., `code/`, `network/`, `system/`, `cybersecurity/`). Each domain has:
- Tool classes (e.g., `CodeTools`, `NetworkTools`)
- `tool_definitions.py` with Ollama function schemas
- All definitions aggregated in `src/utils/core/all_tool_definitions.py`

**ToolRegistry** (`src/utils/core/tool_registry.py`) maps tool names to implementations and routes by agent type. Agent type (code, network, system, cybersecurity, orchestrator) determines which tools + prompts are loaded from `prompts/<domain>/default_<domain>.json`.

**Confirmation gates**: State-modifying tools (`write_file`, `delete_file`, `run_command`, `git_commit`, `git_push`) require explicit user approval unless `--auto` mode is active. Critical paths (env files, CI workflows) always force human approval.

### Core Services (Injected)

Located in `src/utils/core/` and `src/services/`:
- **OllamaClient**: HTTP client for Ollama API; `chat()` returns `(response_data, usage_stats)` tuple
- **FileManager**: File CRUD operations with validation
- **CommandExecutor**: Shell execution with sandbox levels (`limited`/`full`)
- **GitManager**: Git operations (clone, commit, push, branch)
- **CodeAnalyzer**: Language detection, AST parsing, dependency mapping
- **MemoryManager**: Persistent conversation + ChromaDB reasoning cache
- **TokenTracker**: Token usage monitoring per model/role
- **LLMResponseParser**: Strips markdown fences when models ignore raw-content instructions
- **FileValidator**: Validates generated files by extension; delegates to language-specific validators in `src/utils/core/validators/`
- **ModelRouter**: Routes prompts to specialist models; uses Senior Reviewer pattern to select best solution
- **EventPublisher**: Decoupled event dispatch (agent → web UI)
- **LoopDetector**: Semantic similarity-based stuck-agent detection

### Configuration & Models

Configuration is loaded at startup (path specified via CLI or environment). Model selection per task type:
- `models.coding` — code generation (default: `qwen3-coder-next`)
- `models.reasoning` — complex reasoning (default: `gpt-oss:20b`)
- `models.orchestration` / `models.summarization` — lightweight tasks (default: `ministral-3:8b`)
- `models.embedding` — semantic similarity (default: `all-minilm`)

For AutoAgent, see `auto_agent_llms` and `auto_agent_timeouts` in config: maps roles (planner, prototyper, coder, generalist, suggester, senior_reviewer) to models + timeout (seconds).

### AutoAgent Pipeline (8 Phases)

Each phase delegates to a module in `src/utils/domains/auto_generation/`:

| Phase | Module | LLM Role | Purpose |
|-------|--------|----------|---------|
| 1 | `project_planner.py` | planner | Generate project README |
| 2 | `structure_generator.py` | prototyper | Design directory structure |
| 3 | (inline) | — | Create scaffolding |
| 4 | `file_content_generator.py` | prototyper | Generate file content; select related files contextually |
| 5 | `file_refiner.py` | coder | Refine implementation |
| 5.5 | `file_completeness_checker.py` | coder | Validate completeness; retry invalid files |
| 6 | `project_reviewer.py` | generalist | Quality review |
| 7 | `improvement_suggester.py` + `improvement_planner.py` | suggester + planner | Suggest improvements |
| 8 | `senior_reviewer.py` | senior_reviewer | Final selection among multiple solutions |

**Key patterns**:
- Prompts instruct models to output raw content (no markdown); `LLMResponseParser.extract_raw_content()` handles fences
- Cross-file context selection scans related files (backend for frontend, src for dependencies) rather than just last N
- Dependency reconciliation scans real Python imports; regenerates `requirements.txt` when hallucinated packages detected

### Web UI

[src/web/app.py](src/web/app.py) launces Flask on port 5000 with two features:

- **Chat** (`/api/chat`, `/api/chat/stream/<id>`): Interactive DefaultAgent with streamed tool-calling via SSE
- **Project Generation** (`/api/projects/`): AutoAgent pipeline with live log streaming

Architecture: Flask blueprints (`src/web/blueprints/`) + services (`src/web/services/`):
- `ChatEventBridge`: Thread-safe queue bridging agent → SSE endpoint
- `ChatSessionManager`: Per-session DefaultAgent instances (auto_confirm=True in web mode)
- DefaultAgent accepts optional `event_bridge` parameter to emit events during `chat()`

## Build and Test

### Setup
```bash
# Create virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Running Agents
```bash
# Interactive chat (DefaultAgent)
python run_agent.py --chat

# Single instruction
python run_agent.py "your instruction here"

# Auto-confirm mode (skip approval gates)
python run_agent.py --chat --auto

# Autonomous project generation (AutoAgent)
python auto_agent.py --description "project description" --name project_name --refine-loops 1

# Web UI (chat + project generation)
python run_web.py
# Access: http://localhost:5000

# Benchmark models on project generation
python auto_benchmark.py
python auto_benchmark.py --models model1 model2
```

### Testing
```bash
# All tests (mocked Ollama; no live server needed)
pytest tests/ -v --timeout=120 --ignore=tests/test_ollama_integration.py

# Single test file
pytest tests/test_code_agent_integration.py

# Specific test
pytest tests/test_code_agent_integration.py::TestClassName::test_method_name

# With markers
pytest tests/ -m unit
pytest tests/ -m integration
```

Test markers: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`, `@pytest.mark.cowork`

Mocked fixtures in [tests/conftest.py](tests/conftest.py):
- `mock_ollama_client` — patches OllamaClient with mock responses (varying embeddings to avoid false loop detection)
- `temp_project_root` — creates temp directory with config + prompt files for all agent types
- `default_agent` — fully constructed DefaultAgent with mocked Ollama

**Integration tests** (`tests/test_ollama_integration.py`) require live Ollama—skipped in CI. Set `OLLAMA_TEST_URL` and `OLLAMA_TEST_TIMEOUT` environment variables.

### Linting
```bash
ruff check src/ tests/
ruff format src/ tests/  # auto-format
```

### Environment Variables
| Variable | Purpose | Default |
|----------|---------|---------|
| `OLLASH_OLLAMA_URL` | Ollama server (runtime + Docker) | `http://localhost:11434` |
| `OLLAMA_TEST_URL` | Ollama URL for integration tests | `http://localhost:11434` |
| `OLLAMA_TEST_TIMEOUT` | Integration test timeout (seconds) | `300` |
| `PYTHONPATH` | Must include project root for imports | (set in CI via GITHUB_ENV) |

## Project Conventions

### Custom Patterns

1. **Lazy Tool Loading**: Tools are NOT instantiated at startup. They are loaded on first use via `_get_tool_from_toolset()` and cached. Preserve this when adding tools—do not instantiate tools in agent `__init__`.

2. **Domain-Based Prompts**: Each agent type loads a curated prompt + tool subset from `prompts/<domain>/default_<domain>.json`. When adding a tool, register it in the appropriate prompt file + `ToolRegistry.TOOL_MAPPING`.

3. **Cross-File Context Selection**: AutoAgent content generation selects related files contextually (frontend-to-backend dependencies, source files matching imports) rather than sliding windows. See `RAGContextSelector` in `src/utils/core/scanners/`.

4. **Semantic Loop Detection**: Agents detect stuck loops by embedding similarity (via `all-minilm`). If 3 consecutive iterations have >95% similarity, trigger human approval gate. Respects `LOOP_DETECTION_THRESHOLD`, `LOOP_SIMILARITY_THRESHOLD`, `STAGNATION_TIMEOUT_MINUTES` in `src/utils/core/constants.py`.

5. **Model Hybridity**: Different specialist models are selected per task type (reasoning, coding, summarization, embedding). Model + timeout per role; see `config/` for settings.

6. **Token Context Management**: At 70% token capacity, agents trigger summarization of conversation history. See `CONTEXT_SUMMARIZATION_THRESHOLD` in `src/utils/core/constants.py`.

7. **Confirmation Gates**: State-modifying tools require explicit approval unless `--auto` mode active. Critical paths (env, CI) always force approval. See `confirmation_gate()` in DefaultAgent.

### Critical Not-To-Do
- ❌ Do NOT instantiate tools in agent constructors—respect lazy loading
- ❌ Do NOT use raw `print()` for operational logging—use `AgentLogger`
- ❌ Do NOT sidestep `FileManager` for file operations—it handles validation
- ❌ Do NOT bypass `CommandExecutor` for shell commands—it enforces sandbox policy
- ❌ Do NOT remove `LoopDetector` checks—they prevent infinite loops

## Integration Points

### Ollama/OllamaClient
Tools invoke `self.ollama_client.chat(messages, model, timeout, tools=...)` which returns `(response_data, usage_stats)`. Prompts instruct models to output raw content (no markdown); parse via `LLMResponseParser.extract_raw_content()` if models ignore this.

### Tool System Workflow
1. Agent calls `_get_tool_from_toolset(tool_name)` → lazy-loads + caches
2. Tool executes; checks if state-modifying (write/delete/git/run) → confirmation gate
3. Tool result goes to `event_publisher.publish()` for UI consumption
4. Next iteration: agent reviews result + decides next tool/response

### Event Publishing (Web UI)
DefaultAgent can accept optional `event_bridge` parameter (see `ChatEventBridge` in web UI). During `chat()`, it publishes:
- `tool_call` — tool selected + args
- `tool_result` — execution result
- `iteration` — loop progress
- `final_answer` — LLM final response
- `error` — exceptions

### Memory & Knowledge Workspace
`MemoryManager` persists conversation history as JSON + ChromaDB semantic cache. Use `memory_manager.save_context()` after significant interactions. RAG context selection uses `RAGContextSelector` to find relevant past interactions.

## Security & Critical Warnings

- **Sandbox policy**: `CommandExecutor` respects `sandbox_level` (limited/full). Limited forbids dangerous commands (`rm -rf /`, etc.)
- **Permission profiles**: `PermissionProfileManager` restricts tool access per role/user. See `src/utils/core/permission_profiles.py`
- **File validation**: `FileValidator` validates generated files by extension; delegates to language-specific validators. Invalid files trigger retry.
- **Policy enforcement**: `PolicyEnforcer` checks compliance before tool execution (env files, CI workflows always require approval)

## Recommended Files to Review

When onboarding or adding features:
1. [CLAUDE.md](CLAUDE.md) — detailed architecture + commands
2. [src/agents/core_agent.py](src/agents/core_agent.py) — abstract base; shared services
3. [src/agents/default_agent.py](src/agents/default_agent.py) — interactive orchestrator
4. [src/agents/auto_agent.py](src/agents/auto_agent.py) — project generation pipeline
5. [src/utils/core/tool_registry.py](src/utils/core/tool_registry.py) — tool-to-implementation mapping
6. [src/utils/core/constants.py](src/utils/core/constants.py) — thresholds, timeouts, defaults
7. [tests/conftest.py](tests/conftest.py) — test fixtures + mocking patterns
