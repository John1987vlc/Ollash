# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is Ollash

Ollash is a local AI agent platform powered by Ollama. It combines a multi-phase Auto-Agent project generation pipeline with a live multi-agent swarm (Agent-per-Domain) and exposes both a Flask Web UI and a CLI. All LLM calls go to a local Ollama instance (default: `qwen3-coder:30b` for coding, `ministral-3:3b` for planning).

## Key Commands

```bash
# Start
python run_web.py                 # Web UI on port 5000
python ollash_cli.py chat         # CLI chat session

# Testing
pytest tests/unit/                # Unit tests only
pytest tests/integration/         # Integration tests
pytest tests/unit/backend/agents/auto_agent_phases/test_file_content_generation_phase.py  # Single test file
pytest -k "test_my_function"      # Single test by name
pytest tests/e2e/ -m e2e          # E2E tests (requires running server + Playwright)

# Quality
ruff check . --fix                # Lint + auto-fix
ruff format .                     # Format
flake8 backend/ frontend/ tests/  # Style check
playwright install chromium       # Install E2E browsers

# Docker
docker-compose up --build
```

## Architecture

### Entry Points
- **`run_web.py`** → `frontend/app.py` (Flask factory) → registers all blueprints
- **`ollash_cli.py`** → CLI commands: `agent`, `swarm`, `security-scan`, `benchmark`, `chat`
- **`backend/agents/auto_agent.py`** → standalone multi-phase project generator

### Dependency Injection (`backend/core/containers.py`)
All services are wired via `dependency-injector`. The hierarchy is:

```
ApplicationContainer
└── CoreContainer
    ├── LoggingContainer    → core.logging.logger, core.logging.agent_kernel, core.logging.event_publisher
    ├── StorageContainer    → core.storage.file_manager, core.storage.response_parser, core.storage.fragment_cache
    ├── AnalysisContainer   → core.analysis.code_quarantine, core.analysis.dependency_graph, core.analysis.rag_context_selector, core.analysis.vulnerability_scanner
    ├── SecurityContainer   → core.security.permission_manager, core.security.policy_enforcer
    └── MemoryContainer     → core.memory.error_knowledge_base, core.memory.episodic_memory
```

Use the full dotted path — `core.logging.logger`, NOT the old `core.logger`. Override in tests via `main_container.core.logging.logger.override(mock)`.

### Agent Architecture (`backend/agents/`)

**`DefaultAgent`** composes three mixins on top of `CoreAgent`:
- `IntentRoutingMixin` — routes to the right model role based on intent keywords
- `ToolLoopMixin` — handles the tool-call → execute → observe loop
- `ContextSummarizerMixin` — summarizes context when approaching `max_context_tokens`

**`AutoAgent`** orchestrates a sequential 22-phase pipeline:
```
ReadmeGeneration → StructureGeneration → LogicPlanning → StructurePreReview
→ EmptyFileScaffolding → FileContentGeneration → FileRefinement
→ JavaScriptOptimization → Verification → CodeQuarantine
→ SecurityScan → LicenseCompliance → DependencyReconciliation
→ TestGenerationExecution → InfrastructureGeneration
→ ExhaustiveReviewRepair → FinalReview → CICDHealing
→ DocumentationDeploy → IterativeImprovement → DynamicDocumentation
→ ContentCompleteness → SeniorReview
```

All phases inherit from `IAgentPhase` (`auto_agent_phases/base_phase.py`). Override `run()`, declare `REQUIRED_TOOLS`. The `PhaseContext` singleton (`phase_context.py`) carries shared state (LLM manager, file manager, generators) across all phases.

**Domain Agent Swarm** (`backend/agents/domain_agents/`): `DomainAgentOrchestrator` dispatches to `ArchitectAgent`, `DeveloperAgent` (pool of 3), `AuditorAgent`, `DevOpsAgent`. Shared state via `Blackboard`. Supports `SelfHealingLoop`, `DebateNodeRunner` (Architect vs Auditor), and `CheckpointManager`.

### Tool System (`backend/utils/core/tools/` + `backend/utils/domains/`)

Register tools with the `@ollash_tool` decorator:
```python
@ollash_tool(
    name="my_tool",
    description="...",
    parameters={"prop": {"type": "string", "description": "..."}},
    toolset_id="my_tools",
    agent_types=["code", "system"],
    is_async_safe=True,
)
async def my_tool_impl(self, prop: str) -> str: ...
```

`tool_registry.py` auto-discovers tools by walking `backend/utils/domains/**/*.py` at startup — no manual registration needed. Domain toolsets: `file_system_tools`, `command_line_tools`, `network_tools`, `system_tools`, `cybersecurity_tools`, `git_tools`, `auto_generation`.

### LLM Client (`backend/utils/core/llm/`, `backend/services/language_manager.py`)

`LLMClientManager` maps agent role strings to `OllamaClient` instances. Role→model mapping is in `backend/config/llm_models.json` under `agent_roles`. To get a client: `manager.get_client("coder")`. `OllamaClient` supports both `chat()` (sync) and `achat()` (async), function calling via `tools=` param, and built-in token tracking.

### Code Generation Pipeline

- **`EnhancedFileContentGenerator`** (`backend/utils/domains/auto_generation/enhanced_file_content_generator.py`) — creates new files using logic plans + optional RAG context
- **`CodePatcher`** (`backend/utils/domains/auto_generation/code_patcher.py`) — edits existing files using `difflib.SequenceMatcher` (not length/brace heuristics)
- **`StructureGenerator`** (`backend/utils/domains/auto_generation/structure_generator.py`) — generates project scaffolding from a description

### Prompt System (`prompts/`)

YAML files organized by domain. Each file has named prompt templates with `system:` and `user:` keys using `{variable}` placeholders. Loaded by `PromptLoader` singleton (DB-first via SQLite `PromptRepository`, then filesystem fallback):

```yaml
file_gen_v2:
  system: |
    # CONTEXT ...
  user: |
    ## FILE: {file_path}
    ## PURPOSE: {purpose}
```

Key prompt files: `prompts/domains/auto_generation/code_gen.yaml`, `planning.yaml`, `structure.yaml`, `refinement.yaml`.

### Frontend (`frontend/`)

Flask blueprint-based SPA. Blueprints in `frontend/blueprints/` (20+ endpoints): `auto_agent_bp`, `chat_bp`, `analysis_bp`, `benchmark_bp`, `audit_bp`, `checkpoints_bp`, `cicd_bp`, etc. Templates in `frontend/templates/`, scoped assets in `frontend/static/`. Real-time updates flow via `EventPublisher` → WebSocket/SSE to the browser.

### Configuration

| File | Purpose |
|------|---------|
| `backend/config/llm_models.json` | Ollama URL, default model, per-role model assignments |
| `backend/config/tool_settings.json` | Sandbox level, max context tokens, rate limits, parallel concurrency |
| `backend/config/agent_features.json` | Feature flags for optional agent capabilities |
| `.env` | `OLLAMA_URL` and other secrets (never commit) |

## Coding Conventions

- **Type hints required** on all functions. Use `typing` + Pydantic v2.
- **No `print()` for logs** — use `AgentLogger`.
- **No circular imports** — use `backend/interfaces/` to break cycles.
- **Tests mirror `backend/` structure** — `tests/unit/backend/agents/` mirrors `backend/agents/`.
- **Unit tests**: mock all I/O; mark with `@pytest.mark.unit`. Integration tests: `@pytest.mark.integration`.
- When patching a lazily-imported class inside a function, patch at the source module path (e.g., `backend.utils.core.preference_manager_extended.PreferenceManagerExtended`).

## Security

- All state-modifying tools (`write_file`, `run_command`) go through the confirmation gate in `backend/utils/core/system/confirmation_manager.py`.
- `CommandExecutor` uses sandbox levels (from `tool_settings.json`). Do not bypass.
- `PolicyEnforcer` (injected via `core.security.policy_enforcer`) intercepts all shell commands.
