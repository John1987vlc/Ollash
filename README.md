# Ollash — Local AI IT Agent

**Ollash** is an advanced, locally-hosted AI platform that orchestrates specialized agents to autonomously handle software engineering, system administration, cybersecurity, and DevOps tasks. All computation runs on your machine via [Ollama](https://ollama.ai) — no external APIs required.

[![CI/CD](https://github.com/your-org/ollash/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/your-org/ollash/actions/workflows/ci.yml)

---

## v2.0.0 — Agent-per-Domain Architecture

The platform has been rebuilt around a **multi-agent pipeline** where every generation task is routed to the right specialist:

| Agent | Role |
|---|---|
| **ArchitectAgent** | Plans the project as a `TaskDAG` — nodes are files, edges are dependencies |
| **DeveloperAgent** (pool) | Generates source code concurrently, one task per agent |
| **DevOpsAgent** | Produces Dockerfiles, CI/CD configs, Terraform |
| **AuditorAgent** | Security-scans the full output and reports vulnerabilities |

### Fixes & Improvements (Sprint 5)

| # | Fix | Details |
|---|---|---|
| A1 | **Race-condition fix** | `get_ready_tasks()` is now `async` and acquires `asyncio.Lock` before mutating task state |
| A2 | **Fair load-balancing** | Developer pool backed by `asyncio.Queue` — agents check out and return so slow tasks don't starve fast ones |
| A3 | **LLM timeout guard** | Every `agent.run()` is wrapped in `asyncio.wait_for(…, timeout=300s)` to prevent indefinite hangs |
| A4 | **Blackboard memory fix** | `Blackboard.subscribe()` now returns an `unsubscribe()` callable — callers can clean up their callbacks |
| B1 | **CLI wired to new stack** | `ollash agent` now invokes `DomainAgentOrchestrator` with `--pool-size` and `--timeout` flags |
| B2 | **SSE multiagent events** | `ChatEventBridge` subscribes to `task_status_changed`, `domain_orchestration_*`, `file_generated` |

---

## v1.9.0 — Frontend Overhaul

### Project Wizard — Full Configuration
The **Create Project** wizard exposes every CLI option directly in the UI:

**Step 2 — Agent Configuration (always visible):**
- License type (MIT, Apache-2.0, GPL-3.0, BSD-3-Clause, Proprietary)
- Python version, Docker/Terraform toggles, Refinement loops slider
- GitHub integration + Auto-Healing job

**Advanced Accordion (⚙️ Opciones Avanzadas — collapsed by default):**

*Agentes & Rendimiento:*
- **Pool size** (1–5 parallel Developer Agents)
- **Per-task timeout** (60–600 s)
- **Parallel generation** toggle

*Calidad & Seguridad:*
- Security scanning, critical-block gate, checkpoints, cost tracking
- Senior review as PR, GitHub Wiki/Pages

*Feature Flags:*
- Feedback refinement, Refactoring agent, Load testing, Deep license scanning, CI/CD auto-healing

### Kanban Real-time Board
The wizard Kanban board is wired to live `task_status_changed` SSE events — cards move between **Todo / In Progress / Done** as agents work.

### CSS Consistency Overhaul
All ~30 page CSS files audited and normalized:

- **`components/buttons.css`** — bare `<button>` elements reset so browser defaults (Win95 look) can't leak through; all `.btn-*` variants defined once
- **`components/forms.css`** (new) — `.form-input`, `.form-select`, `.form-textarea`, `.form-label`, `.form-group`, `.form-hint`, `.form-row` available everywhere
- **Design token compliance** — hardcoded hex colors, `px` spacing, and `border-radius` replaced with `--color-*`, `--spacing-*`, `--radius-*` CSS variables from `variables.css`
- **16 priority templates** updated: all `<button>` tags have `.btn` base class, all `<input>`/`<select>`/`<textarea>` have canonical form classes

---

## 🚀 Key Features

- **Autonomous Project Generation** — From a single description to a full codebase (frontend, backend, tests, Docker, CI/CD) with self-healing and iterative refinement
- **Agent-per-Domain Architecture** — Architect, Developer pool, DevOps, and Auditor agents collaborate via a `TaskDAG` and shared `Blackboard`
- **Real-time Visibility** — SSE streams push task status, pipeline phase, and generated file events to the UI Kanban board as they happen
- **Continuous Auto-Healing** — Scheduled audits (1–24 h) detect regressions and autonomously fix them
- **Security by Default** — `VulnerabilityScanner` runs on every generated project; critical findings block output
- **Centralized Prompt Management** — All system prompts in YAML files under `prompts/` — edit behavior without touching Python
- **Full DevOps Pipeline** — Semantic versioning, Conventional Commits, GitHub Actions, Docker, optional Terraform

---

## v1.5.0 — Agentic Auto Mode

| # | Enhancement | Description |
|---|---|---|
| E1 | **Incremental Differential Analysis** | Hash-based file tracking — only re-analyzes changed files each cycle |
| E2 | **Auto Tech Stack Detection** | Parses `requirements.txt`, `package.json`, `pyproject.toml` for framework-aware prompt hints |
| E3 | **Auto Quality Monitoring** | Test + linter gate after every loop; auto-heal sub-loop (up to 3 attempts) |
| E4 | **Risk-Based Prioritization** | VulnerabilityScanner feeds into improvement order — critical CVEs fixed first |
| E5 | **Git Event Trigger** | Daemon polls `git diff --numstat`; reschedules the next run on external push |
| E6 | **Execution History Persistence** | Last 50 `ExecutionRecord` entries stored in `tasks.json`; previous errors surfaced at cycle start |
| E7 | **Dynamic Documentation** | Phase 7.5 auto-generates CHANGELOG.md, ROADMAP.md, and refreshes README after each cycle |
| E8 | **File Locking** | `LockedFileManager` — per-path `threading.Lock` + `asyncio.Lock` prevent concurrent write corruption |
| E9 | **Sandbox Validation** | `SandboxValidator` syntax-checks files before writing; rejected content saved as `.candidate` |

---

## 🛠️ Installation

```bash
# 1. Clone
git clone https://github.com/your-org/ollash.git
cd ollash

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp .env.example .env            # set OLLAMA_URL=http://localhost:11434

# 5. Pull a model
ollama pull qwen3:30b

# 6. Start the Web UI
python run_web.py               # → http://localhost:5000
```

---

## 💻 CLI Usage

```bash
# Generate a project with the multi-agent pipeline
python ollash_cli.py agent "Build a FastAPI REST API with SQLite" \
    --name my-api \
    --pool-size 3 \
    --timeout 300

# Security scan
python ollash_cli.py security scan ./my-project/

# Generate tests
python ollash_cli.py test-gen src/app.py

# Schedule recurring maintenance
python ollash_cli.py cron add "0 */6 * * *" "Review and fix my-api"
```

---

## 🧪 Testing & Quality

```bash
# Unit tests (no external services)
pytest tests/unit/ -m "not e2e" -v

# Integration tests
pytest tests/integration/ -v

# E2E tests (requires running server)
pytest tests/e2e/ -m e2e -v

# Lint + format
ruff check backend/ frontend/ tests/ --fix
ruff format backend/ frontend/ tests/
```

**CI/CD Pipeline** (`.github/workflows/ci.yml`):

```
lint ────────────────────── fast gate (syntax) → full ruff + flake8 + mypy
unit-tests ──┬── integration-tests   (parallel, after unit pass)
             └── e2e-tests            (parallel, after unit pass — Playwright)
security ───── Bandit SAST + Safety SCA (informational)
```

Runs on **Python 3.10 and 3.11**. Coverage uploaded as CI artifact on every `master` push. Generated test artifacts cleaned up automatically after each job.

---

## 📐 Architecture

```
ollash/
├── backend/
│   ├── agents/
│   │   ├── orchestrators/
│   │   │   ├── task_dag.py              # TaskDAG + asyncio.Lock + TaskStatus FSM
│   │   │   └── blackboard.py            # Shared KV store + pub/sub with unsubscribe
│   │   ├── domain_agent_orchestrator.py # Multi-agent runner (asyncio.Queue pool)
│   │   ├── architect_agent.py
│   │   ├── developer_agent.py
│   │   ├── devops_agent.py
│   │   └── auditor_agent.py
│   ├── core/containers.py               # dependency-injector DI container
│   └── utils/domains/auto_generation/   # EnhancedFileContentGenerator, CodePatcher
├── frontend/
│   ├── services/chat_event_bridge.py    # SSE push for all agent events
│   ├── static/css/components/
│   │   ├── buttons.css                  # Canonical button system
│   │   └── forms.css                    # Canonical form system (new)
│   └── templates/pages/create_project.html  # 3-step wizard + config accordion
├── tests/
│   ├── unit/                            # Mirrors backend/ + frontend/ structure
│   ├── integration/
│   └── e2e/                             # Playwright browser tests
├── prompts/                             # All LLM prompts as YAML files
├── ollash_cli.py                        # Enterprise CLI entry point
└── .github/workflows/ci.yml            # CI/CD pipeline
```

### Agent-per-Domain Data Flow

```
User → "Build a FastAPI project"
         │
         ▼
  ArchitectAgent.plan_dag()
  → TaskDAG: [main.py] → [tests/] → [Dockerfile] → [audit]
         │
         ▼
  DomainAgentOrchestrator._execution_loop()
  → asyncio.Queue pool dispatches ready tasks
  → DeveloperAgent × N (parallel)
  → DevOpsAgent
  → AuditorAgent
         │
         ▼
  Blackboard (shared KV + pub/sub)
  → publishes task_status_changed events
         │
         ▼
  ChatEventBridge → SSE → Kanban UI (Todo → In Progress → Done)
```

---

## 🤝 Contributing

1. Fork → feature branch (`feat/my-feature`)
2. Follow [Conventional Commits](https://www.conventionalcommits.org/)
3. Run `ruff check . --fix && pytest tests/unit/ -m "not e2e"` before pushing
4. Open a PR against `master`

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
