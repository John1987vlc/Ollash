# <img src="Ollash.jpg" width="48" height="48" valign="middle"> Ollash — Local AI Agent Platform

**Ollash** is a local AI agent platform powered entirely by **Ollama**. It combines a multi-phase **Auto-Agent** project generation pipeline with a live **multi-agent swarm** (Agent-per-Domain), exposes both a **FastAPI Web UI** and a **CLI**, and is optimised to run high-quality code generation on consumer-grade hardware with models as small as 4B parameters.

> All LLM calls go to a local Ollama instance. No cloud APIs, no data leaves your machine.

---

## 🚀 Key Features

### 🏗️ Auto-Agent — Multi-Phase Project Generator

Generate complete, production-ready projects from a single description through a rigorously sequenced pipeline with **adaptive phase filtering** based on model tier:

| Tier | Model range | Phases active |
|------|-------------|---------------|
| **micro** | ≤ 2B (e.g. `qwen3.5:0.8b`) | Core pipeline only (9 heavy phases skipped) |
| **small** | 3–8B (e.g. `qwen3.5:4b`, `custom-coder:7b`) | Full pipeline minus docs/CI/interactive phases |
| **slim** | 9–29B | Full pipeline minus documentation deploy and CICD healing |
| **full** | ≥ 30B (e.g. `qwen3-coder:30b`) | All phases active |

Core phase sequence (24 phases):
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

### 🧠 Domain Agent Swarm

A live cooperative swarm dispatched by `DomainAgentOrchestrator`:

- **ArchitectAgent** — project structure and tech-stack decisions
- **DeveloperAgent** (pool of 3) — parallel code generation and patching
- **AuditorAgent** — security scans and code quality reviews
- **DevOpsAgent** — CI/CD and infrastructure generation

Shared state flows through a `Blackboard`. The swarm supports `SelfHealingLoop`, `DebateNodeRunner` (Architect vs Auditor), and `CheckpointManager`.

### 🌐 Modern Web UI — FastAPI + Vite SPA

- **Real-time Chat** with tool-calling and SSE streaming
- **Architecture Visualizer** — dynamic project graph (Cytoscape)
- **Intelligence Hub** — RAG Knowledge Base, Episodic Memory, Error Patterns
- **Time Machine** — git-backed project checkpoints
- **Ops Center** — background jobs, automation triggers, system health
- **Model Benchmarker** — compare local model tiers
- **Prompt Studio** — live prompt editing and versioning
- **Cost Analyzer** — token usage tracking and model downgrade suggestions
- **HIL DAG Dashboard** — Human-in-the-Loop task interception

---

## ⚡ Quick Start

### Prerequisites

1. Install [Ollama](https://ollama.ai/)
2. Pull the recommended models:

```bash
# Core models (required)
ollama pull qwen3.5:4b            # default — planner, generalist, orchestration
ollama pull qwen3-embedding:4b    # semantic search / RAG

# Optional tiers
ollama pull qwen3.5:0.8b          # micro tasks (writer, suggester, nano_reviewer)
ollama pull qwen3-coder:30b       # senior reviewer, supervisor (needs 20+ GB VRAM)
```

> Your custom `custom-coder:7b` model is used automatically for the `coder` and `test_generator` roles if present in Ollama.

### Installation

```bash
git clone https://github.com/your-repo/ollash.git
cd ollash

python -m venv venv
source venv/bin/activate       # Windows: .\venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env: set OLLAMA_URL=http://localhost:11434
```

### Running

```bash
# Web UI (FastAPI + uvicorn on :5000)
python run_web.py

# CLI chat
python ollash_cli.py chat

# Generate a full project
python ollash_cli.py agent "Create a FastAPI REST API with SQLite and JWT auth" --name my_api

# Run a swarm task
python ollash_cli.py swarm "Audit ./my_project for security issues"

# Security scan
python ollash_cli.py security-scan ./my_project

# Benchmark model tiers
python run_phase_benchmark_custom.py
```

---

## 📂 Project Structure

```text
ollash/
├── backend/
│   ├── agents/
│   │   ├── auto_agent.py                    # Pipeline orchestrator
│   │   ├── auto_agent_phases/               # 24 pipeline phases + PhaseContext
│   │   ├── domain_agents/                   # Swarm agents (Architect, Developer, Auditor, DevOps)
│   │   └── core_agent.py                    # Base agent with mixin composition
│   ├── api/
│   │   ├── app.py                           # FastAPI factory (create_app)
│   │   ├── deps.py                          # FastAPI dependency providers
│   │   └── routers/                         # 45 APIRouter files
│   ├── config/
│   │   ├── llm_models.json                  # Ollama URL + per-role model assignments
│   │   ├── tool_settings.json               # Context limits, concurrency, sandbox level
│   │   └── agent_features.json              # Feature flags
│   ├── core/
│   │   └── containers.py                    # Dependency-injector ApplicationContainer
│   ├── services/
│   │   └── language_manager.py              # LLMClientManager, OllamaClient
│   └── utils/
│       ├── core/
│       │   ├── llm/                         # LLMResponseParser, TokenTracker, PromptLoader
│       │   ├── memory/                      # SQLiteVectorStore, FragmentCache, EpisodicMemory
│       │   └── system/                      # RetryPolicy, CommandExecutor, PolicyEnforcer
│       └── domains/
│           └── auto_generation/
│               ├── planning/                # ProjectPlanner, ImprovementPlanner, …
│               ├── generation/              # EnhancedFileContentGenerator, StructureGenerator, …
│               ├── review/                  # ProjectReviewer, SeniorReviewer, QualityGate, …
│               └── utilities/               # CodePatcher, ProjectTypeDetector, SignatureExtractor, …
├── frontend/
│   ├── templates/                           # Jinja2 HTML templates
│   └── static/                             # CSS, JS (Vite-bundled TypeScript)
├── prompts/                                 # YAML prompt templates per domain
├── tests/
│   ├── unit/                               # 1 500+ unit tests (pytest.mark.unit)
│   ├── integration/                        # Integration tests
│   └── e2e/                               # Playwright E2E tests
└── run_web.py                              # Uvicorn entry point
```

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.10+, FastAPI, Uvicorn, dependency-injector |
| **Database** | SQLAlchemy 2.0 async (SQLite), AsyncSession |
| **Frontend** | TypeScript + Vite, Jinja2 templates |
| **LLM Engine** | Ollama — `qwen3.5:4b` (default), `custom-coder:7b`, `qwen3-coder:30b` |
| **Vector Store** | `SQLiteVectorStore` — zero extra deps, cosine similarity, keyword fallback |
| **Memory** | SQLite — episodic logs, decision tracking, fragment cache |
| **Streaming** | SSE via `asyncio.Queue` + `StreamingResponse` |
| **Testing** | pytest, pytest-asyncio (`asyncio_mode=auto`), Playwright |

> ChromaDB has been fully removed. All vector/RAG functionality runs on the built-in `SQLiteVectorStore`.

---

## ⚙️ Configuration

### `backend/config/llm_models.json` — Model roles

```json
{
  "default_model":  "qwen3.5:4b",
  "embedding":      "qwen3-embedding:4b",
  "agent_roles": {
    "planner":             "qwen3.5:4b",
    "coder":               "custom-coder:7b",
    "nano_coder":          "custom-coder:7b",
    "senior_reviewer":     "qwen3-coder:30b",
    "planner_supervisor":  "qwen3-coder:30b",
    "generalist":          "qwen3.5:4b",
    "analyst":             "qwen3.5:4b",
    "improvement_planner": "qwen3.5:4b",
    "writer":              "qwen3.5:0.8b",
    "suggester":           "qwen3.5:0.8b"
  }
}
```

### `backend/config/tool_settings.json` — Key limits

| Setting | Value | Notes |
|---------|-------|-------|
| `max_context_tokens` | 8192 | Input context budget (4B supports 32K natively) |
| `max_output_tokens` | 4096 | Prevents truncated file generation |
| `parallel_generation_max_concurrent` | 3 | Concurrent file generation tasks |
| `nano_parallel_generation_max_concurrent` | 3 | Same for small/micro models |

Override model size detection without renaming models:
```json
"model_size_overrides": { "coder": 7 }
```

---

## 🔬 4B Model Optimisations

Ollash is built around the assumption that your primary model is **4B parameters** (the "small" tier). All of the following apply automatically when `_is_small_model()` returns `True` and `_is_micro_model()` returns `False`:

| Feature | Behaviour on 4B |
|---------|----------------|
| **Phase filtering** | Skips `ExhaustiveReviewRepair`, `DynamicDocumentation`, `CICDHealing`, `LicenseCompliance`, `Clarification`; keeps `PlanValidation`, `ApiContract`, `TestPlanning`, `ComponentTree` |
| **Temperature** | `0.05` (vs `0.0` for micro, `0.1` for large) |
| **Critic loop** | Enabled — LLM reviews its own output before validation |
| **Auto-heal** | Enabled — `CodePatcher` injects missing functions on semantic warnings |
| **Signatures-only context** | `select_related_files(signatures_only=True)` — only headers, not full files |
| **NanoTaskExpander** | Splits `implement_function` tasks into per-function sub-tasks |
| **Anti-pattern injection** | Error knowledge base warnings always injected |
| **Planner model** | `qwen3.5:4b` — produces significantly better project structures than 0.8B |

### Model tier detection

Detection is based on the size suffix in the Ollama model tag (e.g. `qwen3.5:4b` → 4B):

```
≤ 2B  →  micro  (most aggressive optimisations, active-shadow repair enabled)
3–8B  →  small  (4B default — balanced quality/speed)
9–29B →  slim   (skips docs/CI phases only)
≥ 30B →  full   (all phases active)
```

---

## 🏗️ Architecture — Dependency Injection

All services wired via `dependency-injector`:

```
ApplicationContainer
└── CoreContainer
    ├── LoggingContainer    → core.logging.logger / agent_kernel / event_publisher
    ├── StorageContainer    → core.storage.file_manager / response_parser / fragment_cache
    ├── AnalysisContainer   → core.analysis.code_quarantine / dependency_graph / rag_context_selector
    ├── SecurityContainer   → core.security.permission_manager / policy_enforcer
    └── MemoryContainer     → core.memory.error_knowledge_base / episodic_memory
```

Override in tests:
```python
main_container.core.logging.logger.override(mock_logger)
```

---

## 🛡️ Security & Safety

- **PolicyEnforcer** intercepts all shell commands before execution
- **CodeQuarantine** isolates and analyses suspicious generated snippets
- **VulnerabilityScanner** checks generated code for OWASP top-10 issues
- **Confirmation gate** in `confirmation_manager.py` for all state-modifying tool calls (`write_file`, `run_command`)
- Sandbox levels: `none | limited | strict | docker` (configured in `tool_settings.json`)

---

## 🧪 Testing

```bash
# Unit tests (fast, no Ollama required)
pytest tests/unit/ -q

# Integration tests
pytest tests/integration/ -q

# E2E tests (requires running server + Playwright)
playwright install chromium
pytest tests/e2e/ -m e2e

# Single phase
pytest tests/unit/backend/agents/auto_agent_phases/test_file_content_generation_phase.py
```

Current test suite: **1 553 unit tests**, 2 skipped, 1 xfailed.

---

## 🐳 Docker

```bash
docker-compose up --build
```

---

## 📜 License

MIT License — see [LICENSE](LICENSE) for details.
