# <img src="Ollash.jpg" width="48" height="48" valign="middle"> Ollash — Local AI Agent Platform

**Ollash** is a local AI agent platform powered entirely by **Ollama**. It combines a multi-phase **Auto-Agent** project generation pipeline, a live **multi-agent swarm** (Agent-per-Domain), a **FastAPI Web UI**, an **interactive CLI** (à la Claude Code), and a bidirectional **MCP server/client** — all running 100% on your machine with zero cloud calls.

> All LLM calls go to a local Ollama instance. No cloud APIs. No data leaves your machine. Verifiable via `/api/privacy/audit`.

---

## What's Inside

| Capability | Status |
|---|---|
| **12-phase AutoAgent pipeline**, 4B-optimized — with cross-file contract validation, export validation, duplicate symbol removal + senior review loop | ✅ |
| **11 AutoAgent pipeline improvements** — CSS auto-injection, FastAPI mandatory patterns, JS null guards, DB connection bug detection, smarter complexity scoring | ✅ |
| **Small model pipeline** — TestRunPhase skipped for ≤8B; SeniorReviewPhase runs compact 2-cycle review on all tiers; CrossFileValidationPhase + PatchPhase run on all tiers | ✅ |
| **Quality boost for 4B models** — default 3 refinement loops; focused review aspects (HTML IDs, DOM, event listeners, CSS) always active; SeniorReview compact reads actual file content (≤8 files / ≤32K chars); patch content budget 36K; ruff reports up to 50 errors per pass | ✅ |
| **C# / ASP.NET Core support** — full EF Core rules (AddAsync/Remove, no RemoveAsync), file-scoped namespaces, controller annotations, Program.cs DI patterns; C# static checks in PatchPhase; C# class/interface ref validation in CrossFileValidation | ✅ |
| **Blueprint coverage guard** — files explicitly mentioned in description but absent from blueprint are auto-injected (capped at 3 for small models) | ✅ |
| **8 pipeline fixes (Sprint 14)** — duplicate blueprint paths deduped, api+db file budget boosted, OLLASH_RUN_LOG.md excluded from patch context, key_logic derived for auto-injected files, brace-balance guard on diffs, C# complexity scoring, C# duplicate class detection, CodeFill description limits raised | ✅ |
| **3 pipeline fixes (Sprint 15)** — JS merge skipped when file explicitly named in description; import dedup after merge redirect (prevents `[game.js, game.js]` duplicate signatures); blueprint prompt now requires DOM element IDs in `key_logic` for consistent JS↔HTML wiring | ✅ |
| **Sprint 16 — dead code cleanup + test infrastructure** — 22 backward-compat shim files removed (`auto_generation/` flat level), all 37 import sites migrated to canonical sub-package paths; deprecated `FileContentGenerator` class deleted; `pytest_sessionfinish` hook cleans test-generated dirs on green run; fixture leaks fixed (`fastapi_app` now uses `tmp_path`; `fragment_cache` test uses `tmp_path` fixture) | ✅ |
| **Python constructor arity validation** — CrossFileValidationPhase detects mismatched `__init__` signatures and flags them to PatchPhase | ✅ |
| **Smarter infra generation** — `sys.stdlib_module_names` for accurate stdlib detection; local package names filtered from requirements.txt; Dockerfile assembly name resolved from .csproj | ✅ |
| **Blueprint cache model-keyed** — cache entries from a 4B model are never reused when re-running with a 30B model | ✅ |
| **Sprint 17 — professional output quality** — 6 targeted pipeline fixes from JuegoPokerTexas run log analysis: Pass 10 (HTML inline-script vs JS exports), Pass 11 (JS cross-global calls, large models), blueprint DOM-ID pre-sync, structural-rename bypass in PatchPhase, cross-file context in regeneration prompts, description truncation 400→800/800→1600 | ✅ |
| **Sprint 18 — patch false-positive fix + JS truncation detection** — patch content budget 18K→36K (was misdiagnosing complete files as truncated); JS/TS brace-balance check in CodeFill triggers auto-retry; SeniorReview restored to small-model pipeline (compact 2-cycle review); blueprint requires function signatures for algorithm files; description budget 800→1 200 chars | ✅ **new** |
| **Sprint 18b — SeniorReview & static analysis quality** — SeniorReview content thresholds 20K→32K/40K, file gate 6→8 (5-file JS projects now get content-aware review); compact review issues now carry `file` path for precise patching; ruff error cap 20→50; PatchPhase warns when expected linters (ruff/node/tsc) are not installed | ✅ |
| **Sprint 19 — 9 AutoAgent quality improvements** — 2 new zero-LLM phases (ExportValidationPhase 4c: verifies/repairs declared exports; DuplicateSymbolPhase 4d: removes duplicate JS/TS/Python top-level definitions); CodeFillPhase: real signature tracking, anti-stub guard, JSON/YAML syntax error feedback in retries; PatchPhase: full CrossFileValidation re-check between rounds; SeniorReviewPhase: `"file"` list normalization (fixes 0.2→expected score), zero-LLM security prescan (SQL injection, XSS, eval, hardcoded credentials) | ✅ **new** |
| **Multi-language code generation** — Go, Rust, Java, C#, PHP, Ruby, Kotlin, Dart, SVG + Python/JS/TS | ✅ **new** |
| **Language-specific infra** — `go.mod`, `Cargo.toml`, `pom.xml`, multi-stage Dockerfiles, per-lang `.gitignore` | ✅ **new** |
| **Multi-language static analysis** — `go vet`, `cargo check`, `php -l`, `ruby -c`, HTML link validation | ✅ **new** |
| **Multi-language test runners** — auto-selects `go test` / `cargo test` / `mvn test` / `jest` / `pytest` | ✅ **new** |
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
| 1 267 unit tests + 21 integration tests + 28 E2E passing (Playwright, Ollama-free) | ✅ **new** |
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

### Auto-Agent — 10-Phase Project Generator

Generate complete, production-ready projects from a single description through a **10-phase pipeline** optimized for **4B models** (qwen3.5:4b) with 4K–8K context windows.

Supports **11 languages**: Python, JavaScript/TypeScript, Go, Rust, Java, C#, PHP, Ruby, Kotlin, Dart/Flutter, SVG.

| Tier | Range | Phases |
|------|-------|--------|
| **small** (default) | ≤ 8B (`qwen3.5:4b`) | 9 phases (TestRunPhase skipped; SeniorReviewPhase runs compact 2-cycle review) |
| **full** | > 8B | All 10 phases |

Pipeline:
```
Phase 1:  ProjectScanPhase          — Zero-LLM: detect type/stack, ingest existing files
Phase 2:  BlueprintPhase            — 1 LLM call: full JSON blueprint (max 20 files)
Phase 3:  ScaffoldPhase             — Zero-LLM: create dirs + write stub files
Phase 4:  CodeFillPhase             — Core: generate each file with language-specific system prompts
Phase 4b: CrossFileValidationPhase  — Zero-LLM: HTML↔JS id contract (P1), CSS classes (P2), Python imports (P3),
                                       JS fetch vs routes (P4), form fields vs Pydantic (P5), duplicate window.* (P6),
                                       Python constructor arity (P7), C# class/interface refs (P8),
                                       DB-seeded string case (P9), HTML inline-script vs JS exports (P10),
                                       JS cross-global call validation (P11, large models only)
                                       Auto-fixes id mismatches (similarity > 50%); structural renames seeded to PatchPhase
Phase 5:  PatchPhase                — ruff/tsc/go vet/cargo check/php -l/ruby -c/C# static checks + HTML link validation
                                       id_mismatch/window_function_mismatch → bypass SEARCH/REPLACE, go direct to
                                       full-file regeneration (≤12K chars) with HTML IDs / JS exports injected in prompt
                                       3-round improvement loop; rounds 1+ cycle through 6 focused aspects
Phase 6b: SeniorReviewPhase         — Large: 2-cycle full review + repair (32K context)
                                       Small (≤8B): 2-cycle compact review with actual file content (≤8 files/≤32K chars)
Phase 6:  InfraPhase                — go.mod/Cargo.toml/pom.xml/Dockerfile (multi-stage)/per-lang .gitignore
Phase 7:  TestRunPhase              — Auto-selects go test/cargo test/mvn test/jest/pytest; 3 fix iterations [SKIPPED ≤8B]
Phase 8:  FinishPhase               — Write OLLASH.md, log metrics, fire project_complete event
```

#### Quality pipeline (phases 4b → 5 → 6b)

Three layers of review catch different classes of bugs:

| Layer | Phase | Catches |
|-------|-------|---------|
| **Zero-LLM contract** | 4b CrossFileValidation | ID mismatches (P1), CSS class gaps (P2), Python imports (P3), JS fetch vs routes (P4), form fields vs Pydantic (P5), duplicate window.* (P6), constructor arity (P7), C# refs (P8), DB string case (P9), **HTML inline-script vs JS exports (P10)**, **JS cross-global calls (P11)** |
| **Multi-round improvement** | 5 Patch | Static errors (ruff/tsc/go vet/C# static, up to 50 per run) + 3 LLM rounds; **structural renames bypass SEARCH/REPLACE → direct full-file regen with cross-file context**; 6 focused aspects; content-aware up to 80K / 10 files (36K per reviewer prompt) |
| **Senior architecture review** | 6b SeniorReview | Large models: missing game logic, incomplete state transitions, wrong data flow — auto-repair loop. **Small models**: compact 2-cycle review with actual file content (≤8 files / ≤32K chars); issues include file path for precise CodePatcher targeting. |

#### Language-specific system prompts (CodeFillPhase)

Each language gets a dedicated, rule-enforcing system prompt. Small models (≤8B) use compact variants:

| Language | Extension | Key rules enforced |
|----------|-----------|-------------------|
| **Go** | `.go` | Package decl, grouped imports, `if err != nil`, CamelCase |
| **Rust** | `.rs` | `Result<T,E>` + `?`, ownership rules, no `unwrap()` in prod |
| **Java** | `.java` | Package + all imports, public class matches filename, checked exceptions |
| **C#** | `.cs` | File-scoped namespace (`namespace X;`), EF Core (AddAsync/Remove — no RemoveAsync), `[ApiController]+[Route]`, `AddControllers()` before `MapControllers()` |
| **PHP** | `.php` | `declare(strict_types=1)`, namespaces, PDO for DB |
| **Ruby** | `.rb` | snake_case, iterators, `attr_accessor`, specific `rescue` |
| **Kotlin** | `.kt` / `.kts` | `data class`, `val>var`, `when` expressions, coroutines |
| **Dart/Flutter** | `.dart` | Null safety, `final>var`, `const` constructors, `async`/`await` |
| **SVG** | `.svg` | `xmlns`, `viewBox`, `<defs>`/`<symbol>` reuse, `<use>` references |

#### Language-specific infra plugins (InfraPhase)

| Plugin | Triggers when | Output |
|--------|--------------|--------|
| `GoModPlugin` | `.go` files generated | LLM-generated `go.mod` with real import scan |
| `CargoTomlPlugin` | `.rs` files generated | LLM-generated `Cargo.toml` with crate scan |
| `PomXmlPlugin` | `.java` files generated | LLM-generated `pom.xml` with import scan |
| `DockerfilePlugin` | always | Multi-stage Dockerfiles for Go, Rust, Java, C#, PHP, Ruby, Node, Python |
| `GitignorePlugin` | always | Per-language `.gitignore` (Go/Rust/Java/C#/PHP/Ruby/Dart/Kotlin/Node/Python) |

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
GET  /api/pipelines/phases      → catalog of all 8 phases
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
│   │   ├── auto_agent_phases/               # 10 pipeline phases (scan→blueprint→scaffold→fill→crossvalidate→patch→senreview→infra→testrun→finish)
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
│   ├── unit/                               # 1 226 unit tests (pytest.mark.unit, no Ollama)
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

Ollash is built around **4B parameters** as the primary tier. The 8-phase pipeline is designed to fit within 4K–8K context windows:

| Feature | Behaviour on 4B (≤8B) |
|---------|----------------------|
| Token budget | ~800 tokens system + ~2200 tokens user per LLM call (~4K total); **description visible up to 1 200 chars (small) / 1 600 chars (large)** — full requirements reach the code generator |
| TestRunPhase | **Skipped** — removed from `SMALL_PHASE_ORDER` at orchestrator level |
| SeniorReviewPhase | **Compact 2-cycle review** runs on all tiers — actual file content included for ≤8 files / ≤32K chars; issues carry `file` path for precise repair |
| CrossFileValidationPhase | **Runs** — zero-LLM, catches id mismatches, ctor arity, C# refs |
| Improvement rounds | 3 rounds (matching large models); focused aspects from round 2; content-aware for ≤10 files / ≤80K chars (reviewer prompt budget 36K) |
| Blueprint size | Max 5 files for simple projects; **7 for games/full-stack/React/Flutter/FastAPI web apps** |
| JS merge guard | JS file merge skipped when the file is **explicitly named in the project description** — preserves user-specified multi-file architecture |
| DOM ID consistency | Blueprint prompt enforces `index.html` has **highest priority number** (generated last); JS `key_logic` must list every `#id` accessed; BlueprintPhase auto-injects missing DOM ids from JS into `index.html key_logic` before generation begins |
| CSS auto-injection | `static/style.css` auto-added to blueprint when CSS in stack + HTML planned but no CSS file |
| FastAPI mandatory hints | Large models get a `MANDATORY PATTERNS` block in CodeFill prompts: `StaticFiles`, `startup` event, list endpoints |
| Shared JS null guards | JS imported by multiple HTML pages gets `if (!el) return;` guard instructions |
| Language prompts | Compact single-line variants for Go/Rust/Java/C#/PHP/Ruby/Kotlin/Dart |
| Dynamic token budget | `_estimate_num_predict()` → 4096 tokens for game/logic/engine/solver files, 2048 otherwise |
| Syntax validation | CodeFillPhase validates output and retries once on syntax error; JS/TS brace-balance check catches truncated files before they're written to disk |
| Patching | PatchPhase runs ruff/tsc/go vet/cargo check/php -l/ruby -c + 3-round improvement (focused aspects from round 2) |
| Micro tier (≤2B) | `ctx.is_micro()` — uses even shorter prompt variants |

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
# → 1 267 tests collected

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
| `GET` | `/api/pipelines/phases` | — | Catalog of 10 AutoAgent phases |
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
| `backend/agents/auto_agent_phases/` | [All phases, PhaseContext, Sprint 10–17 improvements](backend/agents/auto_agent_phases/README.md) |
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
