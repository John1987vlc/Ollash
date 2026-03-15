# <img src="Ollash.jpg" width="48" height="48" valign="middle"> Ollash — Local AI Agent Platform

**Ollash** is a local AI agent platform powered entirely by **Ollama**. It combines a multi-phase **Auto-Agent** project generation pipeline, a live **multi-agent swarm** (Agent-per-Domain), a **FastAPI Web UI**, an **interactive CLI** (à la Claude Code), and a bidirectional **MCP server/client** — all running 100% on your machine with zero cloud calls.

> All LLM calls go to a local Ollama instance. No cloud APIs. No data leaves your machine. Verifiable via `/api/privacy/audit`.

---

## What's Inside

| Capability | Status |
|---|---|
| Multi-phase project generator (39 phases, adaptive tier filtering) | ✅ |
| **Interactive Coding Mode** — `DefaultAgent` in chat, read→edit→verify loop | ✅ **new** |
| Interactive CLI with repo context, file editing, tool loop | ✅ |
| Domain Agent Swarm (Architect, Developer ×3, Auditor, DevOps) | ✅ |
| FastAPI Web UI — 51 routers, SSE streaming, Vite bundle | ✅ |
| JWT auth + API keys (local SQLite, no external IdP) | ✅ |
| Pipeline Builder — drag-and-drop, SSE live execution | ✅ |
| MCP server (Ollash exposes tools to Claude Code / Cline) | ✅ |
| MCP client (Ollash consumes external MCP server tools) | ✅ |
| Plugin system — Python files/packages in `~/.ollash/plugins/` | ✅ |
| RAG with `SQLiteVectorStore` — zero extra dependencies | ✅ |
| **Per-session project index** — semantic `search_codebase()` tool | ✅ **new** |
| **Streaming shell output** — live pytest/npm/cargo lines via SSE | ✅ **new** |
| Privacy monitor — network call audit, 🔒 local mode badge | ✅ |
| 1 334 tests — unit · integration · E2E (Playwright, Ollama-free) | ✅ |
| **Security hardening** — CORS, rate limiting, input validation, command injection fixes | ✅ |
| **Unified config** — 9 focused JSON files (≤30 lines each), no JSON-in-env-vars | ✅ **new** |
| **JS MIME fix** — custom StaticFiles subclass, immune to Windows registry override | ✅ **new** |

---

## Quick Start

### Prerequisites

1. Install [Ollama](https://ollama.ai/)
2. Pull the recommended models:

```bash
ollama pull qwen3.5:4b            # default — planner, generalist, orchestration
ollama pull qwen3-embedding:4b    # RAG / semantic search
ollama pull qwen3.5:0.8b          # micro tasks (writer, suggester)
ollama pull qwen3-coder:30b       # senior reviewer (needs ≥20 GB VRAM)
```

### Installation

```bash
git clone https://github.com/your-repo/ollash.git
cd ollash

python -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env: OLLAMA_URL=http://localhost:11434
```

### Running

```bash
# Web UI on :5000
python run_web.py

# Interactive CLI (repo-aware, file editing, tool loop)
python ollash_cli.py chat

# Generate a full project with the 32-phase AutoAgent pipeline
python ollash_cli.py auto-agent "Create a FastAPI REST API with SQLite and JWT auth" --name my_api

# Generate a full project using the Domain Agent Swarm (multi-agent)
python ollash_cli.py agent "Create a FastAPI REST API with SQLite and JWT auth" --name my_api

# Domain Agent Swarm task
python ollash_cli.py swarm "Audit ./my_project for security issues"

# Security scan
python ollash_cli.py security-scan ./my_project

# Expose Ollash tools to Claude Code / Cline via MCP stdio
python -m backend.mcp

# Benchmark model tiers (phase benchmarker)
python run_phase_benchmark_custom.py

# Benchmark via CLI (uses ModelBenchmarker, supports --models filter)
python ollash_cli.py benchmark
python ollash_cli.py benchmark --models qwen3.5:4b qwen3-coder:30b

# Generate multi-language tests for a source file
python ollash_cli.py test-gen backend/agents/auto_agent.py --lang python
```

---

## Security

Ollash runs entirely locally. No data leaves your machine. The following hardening is applied:

| Layer | Control |
|-------|---------|
| **Rate limiting** | `SlowAPIMiddleware` — 300 req/min per IP globally; `/api/auth/login` capped at 10/min (brute-force protection) |
| **CORS** | Defaults to `localhost:5000` only. Set `OLLASH_CORS_ORIGINS` (comma-separated) to expand. `allow_credentials` disabled when wildcard is active. |
| **Command injection** | All `subprocess` calls use `shell=False` with list arguments. User-supplied `repo_name`/`org` are regex-validated before shell invocation. |
| **Path traversal** | `_safe_resolve()` used on all file operations. Knowledge graph and plugin install endpoints restrict paths to workspace subtree. |
| **Input validation** | All Pydantic models include `min_length`/`max_length`/`pattern` constraints. File saves are capped at 10 MB. |
| **Error leakage** | `service_error_handler` returns opaque `ref: <id>` to clients; full tracebacks go to server logs only. |
| **SSRF** | Ollama URL validated against an allowlist (`localhost`, `127.0.0.1`). Extend via `OLLAMA_HOSTS_ALLOWLIST` env var. |
| **Security headers** | `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `Referrer-Policy` on every response. |
| **Plugin install** | Source path restricted to `.ollash/` and `uploads/` — cannot copy arbitrary server files into the plugin dir. |
| **Terminal** | `cd` navigation bounded to workspace `allowed_dirs`; every command is audit-logged (`INFO TERM_EXEC`). |
| **JWT** | `python-jose` validates `exp` claim automatically; tokens expire in 24 h (configurable via `OLLASH_JWT_EXPIRE_HOURS`). |

> **Note:** The terminal WebSocket (`/api/terminal/ws`) has no authentication — only expose Ollash on trusted networks.

---

## Key Features

### Auto-Agent — Multi-Phase Project Generator

Generate complete, production-ready projects from a single description through a sequenced 39-phase pipeline with **adaptive phase filtering** based on model tier:

| Tier | Model range | Active phases |
|------|-------------|---------------|
| **micro** | ≤ 2B (`qwen3.5:0.8b`) | Core pipeline only (9 heavy phases skipped) |
| **small** | 3–8B (`qwen3.5:4b`) | Full minus docs/CI/interactive phases |
| **slim** | 9–29B | Full minus documentation deploy and CI/CD healing |
| **full** | ≥ 30B (`qwen3-coder:30b`) | All phases active |

Core phase sequence:
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

### Interactive Coding Mode — Claude Code-style assistant

Start a coding session against any local project via the Web UI or API:

```bash
# Via API
POST /api/chat
{
  "message": "Fix the failing tests in tests/unit/",
  "mode": "coding",
  "project_path": "/path/to/my-project"
}
```

The session uses `DefaultAgent` (full tool loop) instead of the lightweight `SimpleChatAgent`:

| Capability | Detail |
|---|---|
| **Project tree** auto-injected | The agent knows all source files from the first message |
| **Read files** | `read_file(path, start_line, end_line)` — supports line ranges |
| **Surgical edits** | `apply_unique_edit` — validates uniqueness before replacing, returns diff |
| **Shell streaming** | `run_command_streaming` — live pytest/npm/cargo output via SSE events |
| **Semantic search** | `search_codebase(query)` — RAG over all project files (built in background) |
| **CLAUDE.md / OLLASH.md** | Project-level instructions auto-appended to the system prompt |

Standard agent workflow (enforced by the system prompt):
```
1. read_file → understand current code
2. Propose change (show what will be modified)
3. write_file / apply_unique_edit
4. run_command (pytest / ruff / npm test) → verify
```

### Interactive CLI — à la Claude Code

```bash
python ollash_cli.py chat
```

In the REPL:

| Command | Effect |
|---------|--------|
| `/add <file>` | Add file to active context |
| `/edit <file>` | Propose + apply a diff (with confirmation) |
| `/run <cmd>` | Execute a shell command, stream output live |
| `/model <name>` | Switch Ollama model at runtime |
| `/status` | Show repo stats, active model, token budget |
| `/files` | List files currently in context |
| `/clear` | Clear conversation history |

Features: persistent history (`~/.ollash_history`), slash-command autocomplete, `rich` rendering, tool-call loop display.

### Domain Agent Swarm

Dispatched by `DomainAgentOrchestrator`:

- **ArchitectAgent** — project structure and tech-stack decisions
- **DeveloperAgent** (pool of 3) — parallel code generation and patching
- **AuditorAgent** — security scans and code quality reviews
- **DevOpsAgent** — CI/CD and infrastructure generation

Shared state via `Blackboard`. Supports `SelfHealingLoop`, `DebateNodeRunner` (Architect vs Auditor), and `CheckpointManager`.

### MCP — Bidirectional Protocol Support

**Ollash as MCP server** (exposes tools to Claude Code, Cline, Continue.dev):

```json
{
  "mcpServers": {
    "ollash": {
      "command": "python",
      "args": ["-m", "backend.mcp"],
      "cwd": "/path/to/ollash"
    }
  }
}
```

**Ollash as MCP client** (consumes external MCP servers):

```bash
# Register an external MCP server
POST /api/mcp/servers
{"name": "filesystem", "transport": "stdio", "command": ["npx", "@modelcontextprotocol/server-filesystem", "."]}

# All external tools are automatically merged with Ollash's own tool catalog
GET /api/mcp/tools
```

### Pipeline Builder

Build and run custom pipelines through the web UI:

```
GET  /api/pipelines/phases      → catalog of all 39 phases
GET  /api/pipelines             → list saved pipelines
POST /api/pipelines             → create pipeline (name + phase list)
POST /api/pipelines/{id}/run    → execute with SSE streaming progress
```

4 built-in pipelines: **Quick Review**, **Refactor**, **Full Test**, **Security Audit**.

### Authentication

Local JWT auth — no external IdP required:

```bash
# Register
POST /api/auth/register   {"username": "alice", "password": "secret"}

# Login → JWT Bearer token (24h)
POST /api/auth/login      {"username": "alice", "password": "secret"}

# API keys for programmatic access
POST /api/auth/api-keys   {"name": "my-key"}
# → {"key": "ollash_...", "key_id": 1}
```

All state-modifying endpoints require `Authorization: Bearer <token>` or `Authorization: Bearer ollash_<key>`.

### Privacy Monitor

```bash
GET /api/privacy/status   # No auth — used by UI badge
# → {"is_local": true, "mode": "local", "ollama_url": "...", "allowed_hosts": [...]}

GET /api/privacy/audit    # Requires auth
# → {"summary": {"total_calls": 5, "local_calls": 5, "external_calls": 0, "is_clean": true}, "log": [...]}
```

The web UI shows a **🔒 100% Local** badge (green) or **⚠️ Remoto** (amber) based on this endpoint.

### Plugin System

Drop a `.py` file or Python package into `~/.ollash/plugins/`:

```bash
POST /api/plugins/install   {"source_path": "/path/to/my_plugin.py"}
GET  /api/plugins            # list installed plugins
POST /api/plugins/my_tool/reload  # hot-reload without restart
```

Any `@ollash_tool` decorators in the plugin auto-register into the global tool registry on load.

---

## Project Structure

```text
ollash/
├── backend/
│   ├── agents/
│   │   ├── auto_agent.py                    # Pipeline orchestrator (adaptive phase filtering)
│   │   ├── default_agent.py                 # Chat agent (IntentRouting + ToolLoop + ContextSummarizer)
│   │   ├── auto_agent_phases/               # 39 pipeline phases + PhaseContext singleton
│   │   ├── domain_agents/                   # Swarm: Architect, Developer ×3, Auditor, DevOps
│   │   ├── mixins/                          # ContextSummarizer, IntentRouting, ToolLoop
│   │   └── orchestrators/                   # Blackboard, TaskDAG, SelfHealingLoop, DebateNodeRunner
│   ├── api/
│   │   ├── app.py                           # FastAPI factory (create_app + lifespan DI)
│   │   ├── deps.py                          # FastAPI dependency providers
│   │   ├── vite.py                          # Vite manifest asset URL resolver
│   │   └── routers/                         # 51 APIRouter files (20+ implemented)
│   ├── mcp/
│   │   ├── server.py                        # MCP stdio server (JSON-RPC 2.0)
│   │   ├── client.py                        # MCP client manager (stdio + HTTP transports)
│   │   ├── protocol.py                      # Message builders + tool format converters
│   │   └── server_store.py                  # SQLite registry of external MCP servers
│   ├── config/
│   │   ├── llm_models.json                  # Ollama URL + per-role model assignments
│   │   ├── tool_settings.json               # Context limits, concurrency, sandbox level
│   │   └── agent_features.json              # Feature flags for optional capabilities
│   ├── core/
│   │   ├── containers.py                    # ApplicationContainer (5 semantic sub-containers)
│   │   └── kernel.py                        # AgentKernel — tool execution core
│   └── utils/
│       ├── core/
│       │   ├── analysis/                    # CodeQuarantine, RAGContextSelector, VulnerabilityScanner
│       │   ├── io/                          # FileManager, CheckpointManager, MultiFormatIngester
│       │   ├── llm/                         # OllamaClient, PromptLoader, LLMResponseParser, TokenTracker
│       │   ├── memory/                      # EpisodicMemory, ErrorKnowledgeBase, FragmentCache, SQLiteVectorStore
│       │   └── system/
│       │       ├── db/                      # UserStore, PipelineStore (SQLite, sync)
│       │       ├── network_monitor.py       # Outbound HTTP call tracker (ring buffer, 500 entries)
│       │       ├── retry_policy.py          # RetryPolicy (exponential back-off, sync + async)
│       │       └── trigger_manager.py       # Unified condition/trigger manager
│       └── domains/                         # 11 domain toolsets
│           └── auto_generation/
│               ├── generation/              # EnhancedFileContentGenerator, StructureGenerator
│               ├── planning/                # ProjectPlanner, ImprovementPlanner
│               ├── review/                  # ProjectReviewer, SeniorReviewer, QualityGate
│               └── utilities/               # CodePatcher, ProjectTypeDetector, SignatureExtractor
├── frontend/
│   ├── templates/                           # Jinja2 HTML (base.html + 30+ page partials)
│   └── static/
│       ├── css/                             # Per-page stylesheets
│       ├── js/                              # TypeScript (core/, pages/) + Vite entry
│       └── dist/                            # Vite bundle output (npm run build)
├── prompts/domains/auto_generation/         # YAML prompt templates (DB-first via PromptLoader)
├── tests/
│   ├── unit/                               # 1 334 unit tests (pytest.mark.unit, no Ollama)
│   ├── integration/                        # 20 integration tests
│   └── e2e/                                # 51 Playwright E2E tests (Ollama-free)
├── .github/workflows/ci.yml                # CI: lint → unit → integration + e2e (parallel)
└── run_web.py                              # Uvicorn entry point (:5000)
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.10+, FastAPI, Uvicorn, dependency-injector |
| **Auth** | BCrypt passwords, python-jose JWT (local, no external IdP) |
| **Database** | SQLAlchemy 2.0 async (SQLite), `UserStore`, `PipelineStore` (sync SQLite) |
| **Frontend** | TypeScript + Vite, Jinja2 templates, CDN libs (Cytoscape, Monaco, Chart.js…) |
| **LLM Engine** | Ollama — `qwen3.5:4b` default, adaptive tier selection |
| **Vector Store** | `SQLiteVectorStore` — zero extra deps, cosine similarity + keyword fallback |
| **MCP** | JSON-RPC 2.0 over stdio (server) + stdio/HTTP (client) |
| **Streaming** | SSE via `asyncio.Queue` + `StreamingResponse` |
| **Testing** | pytest + pytest-asyncio (`asyncio_mode=auto`), Playwright, Vitest |

---

## Configuration

All config lives in `backend/config/` as focused JSON files (≤ 30 lines each).
Environment-specific secrets go in `.env` — no JSON strings inside env vars.

| File | Purpose |
|---|---|
| `ollama.json` | Ollama URL, timeout, temperature, num_ctx |
| `models.json` | Model tiers: nano / medium / large / xl / embedding |
| `agent_roles.json` | Per-role model assignments (`planner`, `coder`, …) |
| `tools.json` | Sandbox level, iteration limits, confirm thresholds |
| `runtime.json` | Logging, context tokens, rate limits, encoding |
| `features.json` | Feature flags, knowledge_graph, artifacts, OCR, speech |
| `optimizations.json` | Small-model and mid-model pipeline optimizations |
| `phase_features.json` | Per-phase feature knobs (clarification, api_contract, …) |
| `alert_thresholds.json` | Alert rules (CPU, memory) |
| `security_policies.json` | Command allowlist, path protection, sandbox rules |
| `automation_templates.json` | Trigger definitions |

### Key settings at a glance

| Setting (file) | Default | Notes |
|---|---|---|
| `url` (ollama.json) | `http://localhost:11434` | Override with `OLLAMA_URL` env var |
| `max_context_tokens` (runtime.json) | 8192 | Input context budget |
| `max_output_tokens` (runtime.json) | 4096 | Prevents truncated file generation |
| `parallel_max_concurrent` (tools.json) | 3 | Concurrent file generation tasks |
| `sandbox` (tools.json) | `"limited"` | `none \| limited \| full` |

### `.env` — secrets and overrides only

```bash
OLLAMA_URL=http://localhost:11434   # override ollama.json url
# DEFAULT_MODEL=qwen3.5:4b         # override models.json default
GITHUB_TOKEN=...
SMTP_SERVER=...
```

---

## 4B Model Optimisations

Ollash is built around **4B parameters** as the primary tier. All of the following apply automatically when `_is_small_model()` is `True`:

| Feature | Behaviour on 4B |
|---------|----------------|
| Phase filtering | Skips `ExhaustiveReviewRepair`, `DynamicDocumentation`, `CICDHealing`, `LicenseCompliance`, `Clarification` |
| Temperature | `0.05` (vs `0.0` micro, `0.1` large) |
| Critic loop | Enabled — LLM reviews its own output before validation |
| Auto-heal | `CodePatcher` injects missing functions on semantic warnings |
| Signatures-only context | Only headers injected into context, not full file bodies |
| NanoTaskExpander | Splits tasks into per-function sub-tasks (20–50 lines each) |
| Anti-pattern injection | Error knowledge base warnings always injected |

---

## Architecture — Dependency Injection

All services wired via `dependency-injector`. Use full dotted paths:

```
ApplicationContainer
└── CoreContainer
    ├── LoggingContainer    → core.logging.logger / agent_kernel / event_publisher
    ├── StorageContainer    → core.storage.file_manager / response_parser / fragment_cache
    ├── AnalysisContainer   → core.analysis.code_quarantine / rag_context_selector / vulnerability_scanner
    ├── SecurityContainer   → core.security.permission_manager / policy_enforcer
    └── MemoryContainer     → core.memory.error_knowledge_base / episodic_memory
```

Override in tests:
```python
main_container.core.logging.logger.override(mock_logger)
```

---

## Tool System

Register tools with `@ollash_tool` anywhere under `backend/utils/domains/`. `ToolRegistry` auto-discovers them at startup:

```python
from backend.utils.core.tools.tool_decorator import ollash_tool

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

Domain toolsets: `file_system_tools`, `command_line_tools`, `network_tools`, `system_tools`, `cybersecurity_tools`, `git_tools`, `auto_generation`.

---

## Security & Safety

- **PolicyEnforcer** intercepts all shell commands before execution
- **CodeQuarantine** isolates generated files with critical issues in `.quarantine/`
- **VulnerabilityScanner** checks generated code for OWASP Top-10 issues
- **ConfirmationManager** gates all state-modifying tool calls (`write_file`, `run_command`)
- **NetworkMonitor** tracks every outbound HTTP call — `GET /api/privacy/audit` verifies zero external calls

---

## Testing

```bash
# Unit tests (no Ollama required)
pytest tests/unit/ -q
# → 1 334 passed, 2 skipped, 1 xfailed

# Integration tests
pytest tests/integration/ -q
# → 20 passed, 1 skipped

# E2E tests (Playwright, Ollama-free)
playwright install chromium
pytest tests/e2e/ -m e2e

# Single file
pytest tests/unit/backend/api/test_auth_router.py

# Coverage
pytest tests/unit/ --cov=backend --cov-report=term-missing
```

CI pipeline (`.github/workflows/ci.yml`): `ruff lint → unit tests → integration tests → e2e tests` on every push to `master`.

---

## API Reference (key endpoints)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/auth/register` | — | Create local user account |
| `POST` | `/api/auth/login` | — | Obtain JWT Bearer token |
| `GET` | `/api/auth/me` | ✓ | Current user profile |
| `POST` | `/api/auth/api-keys` | ✓ | Generate API key |
| `GET` | `/api/health/` | — | Ollama connectivity + CPU/RAM |
| `GET` | `/api/privacy/status` | — | Local mode detection |
| `GET` | `/api/privacy/audit` | ✓ | Outbound HTTP call log |
| `GET` | `/api/pipelines/phases` | — | Catalog of 39 phases |
| `GET` | `/api/pipelines` | ✓ | List saved pipelines |
| `POST` | `/api/pipelines` | ✓ | Create pipeline |
| `POST` | `/api/pipelines/{id}/run` | ✓ | Execute pipeline (SSE) |
| `GET` | `/api/mcp/tools` | ✓ | All Ollash tools in MCP format |
| `POST` | `/api/mcp/call` | ✓ | Execute an Ollash tool |
| `GET` | `/api/mcp/status` | ✓ | MCP server info + client connections |
| `GET` | `/api/mcp/servers` | ✓ | List configured external MCP servers |
| `POST` | `/api/mcp/servers` | ✓ | Add external MCP server |
| `GET` | `/api/plugins` | ✓ | List installed plugins |
| `POST` | `/api/plugins/install` | ✓ | Install plugin from local path |

---

## Folder-level Technical Docs

| Directory | Document |
|-----------|---------|
| `backend/` | [Architecture overview](backend/README.md) |
| `backend/agents/` | [Agent types, mixins, tiers](backend/agents/README.md) |
| `backend/agents/auto_agent_phases/` | [All phases, PhaseContext](backend/agents/auto_agent_phases/README.md) |
| `backend/api/routers/` | [All 51 routers](backend/api/routers/README.md) |
| `backend/mcp/` | MCP server/client protocol |
| `backend/utils/core/memory/` | [EpisodicMemory, ErrorKB, SQLiteVectorStore](backend/utils/core/memory/README.md) |
| `backend/utils/core/system/` | [Logger, triggers, RetryPolicy, DB, NetworkMonitor](backend/utils/core/system/README.md) |
| `tests/` | [How to run, fixtures, conventions](tests/README.md) |
| `prompts/` | [YAML format, PromptLoader, small model prompts](prompts/README.md) |

---

## Docker

```bash
docker-compose up --build
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.
