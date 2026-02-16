# Ollash

![Ollash Logo](Ollash.png)

[![CI/CD Pipeline](https://github.com/John1987vlc/Ollash/actions/workflows/ci.yml/badge.svg)](https://github.com/John1987vlc/Ollash/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Ollama Powered](https://img.shields.io/badge/powered%20by-Ollama-blueviolet)](https://ollama.com)

**Ollash** is a modular AI agent framework powered by [Ollama](https://ollama.com) for local IT tasks: code analysis, network diagnostics, system administration, cybersecurity, and autonomous project generation. It orchestrates specialized agents through Ollama's tool-calling API, keeping all inference local and private.

---

## Key Features

- **Interactive CLI** &mdash; Chat-based interface with intent classification, automatic agent-type selection, and semantic loop detection.
- **Autonomous Project Generation (AutoAgent)** &mdash; Generate complete software projects from natural language descriptions using a multi-phase pipeline with 18+ specialized phases.
- **Web UI** &mdash; Flask-based dashboard for chatting with agents, generating projects, monitoring the system, managing automations, and viewing artifacts.
- **Specialized Agents** &mdash; Domain agents for code, network, system, cybersecurity, and orchestration, each with curated prompts and tool sets.
- **Knowledge Workspace** &mdash; ChromaDB-backed RAG context selection, knowledge graph building, cross-reference analysis, and decision memory.
- **Proactive Automation** &mdash; Trigger-based automation with scheduling (APScheduler), real-time alerts, webhook notifications (Slack, Discord, Teams), and system monitoring.
- **Image Generation** &mdash; InvokeAI 6.10+ integration supporting text-to-image and image-to-image with FLUX, Stable Diffusion, Dreamshaper, and Juggernaut XL models.
- **Model Benchmarking** &mdash; Benchmark LLM models on project generation tasks and auto-select the best model per role.
- **Dependency Injection** &mdash; Full DI via `dependency-injector` for testable, modular architecture.

---

## 20 Major Feature Improvements

### Group A — Foundation

| # | Feature | Description | Key Files |
|---|---------|-------------|-----------|
| F2 | **Checkpoint & Resume** | JSON per-project + SQLite index. Save/restore AutoAgent pipeline state after each phase. Resume with `--resume` flag. | `backend/utils/core/checkpoint_manager.py` |
| F16 | **Plugin System** | Third-party extensions via `OllashPlugin` ABC. Auto-discovery in `plugins/` directory. Hot-load/unload, custom tool registration. | `backend/utils/core/plugin_manager.py`, `backend/utils/core/plugin_interface.py`, `plugins/example_plugin/` |
| F8 | **Model Cost Analyzer** | Track token usage per model/phase. Generate cost reports. Suggest cheaper models for trivial tasks. | `backend/utils/core/cost_analyzer.py`, `frontend/blueprints/cost_bp.py` |

### Group B — Core Agents

| # | Feature | Description | Key Files |
|---|---------|-------------|-----------|
| F1 | **Multi-Agent Parallel Orchestration** | Run file generation across multiple LLM instances simultaneously. Dependency-graph-aware task splitting. Configurable via `PARALLEL_GENERATION=true`. | `backend/utils/core/multi_agent_orchestrator.py` |
| F5 | **Long-Term Episodic Memory** | Record errors, solutions, and outcomes. Query past solutions for similar errors. SQLite + JSON persistence. | `backend/utils/core/episodic_memory.py` |
| F17 | **Reinforcement Learning from Feedback** | Thumbs up/down on code blocks. Few-shot prompt injection from positive examples. Adaptive temperature tuning. | `backend/utils/core/prompt_tuner.py`, `backend/utils/core/feedback_store.py` |

### Group C — Code Quality

| # | Feature | Description | Key Files |
|---|---------|-------------|-----------|
| F9 | **Real-Time Vulnerability Scanning** | Pattern-based + AST security scanning. Checks: injection, hardcoded secrets, unsafe deserialization, XSS, SSRF. Blocks critical findings. | `backend/utils/core/vulnerability_scanner.py`, `backend/utils/core/security_rules.py` |
| F20 | **Legal Compliance & License Agent** | Deep license compatibility scanning. Generates `LICENSE_REPORT.md`. Blocks incompatible dependencies. | `backend/utils/core/deep_license_scanner.py`, `backend/utils/core/license_compatibility_matrix.py` |
| F3 | **Proactive Refactoring Agent** | SOLID principle analysis. Automatic refactoring suggestions. Runs after Senior Review phase. | `backend/agents/auto_agent_phases/refactoring_phase.py`, `backend/utils/core/refactoring_analyzer.py` |

### Group D — DevOps

| # | Feature | Description | Key Files |
|---|---------|-------------|-----------|
| F6 | **IaC Generation (Terraform/K8s)** | Dedicated `InfrastructureGenerationPhase`. Terraform modules, K8s manifests, Docker Compose. Triggered via `--include-infra`. | `backend/agents/auto_agent_phases/infrastructure_generation_phase.py`, `backend/utils/domains/auto_generation/infra_generator.py` |
| F18 | **Multilingual Documentation** | Translate README and code comments to multiple languages. `--languages en,es,zh`. Generates `README.{lang}.md`. | `backend/utils/core/doc_translator.py`, `backend/agents/auto_agent_phases/documentation_translation_phase.py` |
| F7 | **CI/CD Auto-Healing** | Analyze CI/CD failure logs. LLM-driven root cause analysis. Generate fix patches. Web UI dashboard. | `backend/utils/core/cicd_healer.py`, `frontend/blueprints/cicd_bp.py` |

### Group E — Frontend & Visualization

| # | Feature | Description | Key Files |
|---|---------|-------------|-----------|
| F11 | **Knowledge Graph Visualizer** | Interactive vis.js force-directed graph. Search, filter, neighborhood exploration. Node detail panel. | `frontend/blueprints/knowledge_graph_bp.py`, `frontend/static/js/knowledge-graph.js`, `frontend/static/css/knowledge-graph.css` |
| F12 | **Live Pair Programming** | Real-time SSE streaming of code generation. Pause/resume agent. User interventions override agent output. Session history. | `backend/utils/core/pair_programming_session.py`, `frontend/blueprints/pair_programming_bp.py`, `frontend/static/js/pair-programming.js` |
| F15 | **Multi-Purpose Export** | Export to ZIP, GitHub, GitLab, Vercel, Railway, Fly.io. Uses `gh` CLI for GitHub. Token-authenticated cloud deploys. | `backend/utils/core/export_manager.py`, `frontend/blueprints/export_bp.py` |

### Group F — Multimedia & UX

| # | Feature | Description | Key Files |
|---|---------|-------------|-----------|
| F4 | **Multimodal UI/UX** | OCR-powered screenshot analysis. LLM-driven UI review phase. Integrates existing `OCRProcessor`. | `backend/utils/core/ui_analyzer.py`, `backend/agents/auto_agent_phases/ui_review_phase.py` |
| F13 | **Advanced Voice Commands** | LLM-based intent classification for complex voice commands. 12 command types. Browser speech API integration. | `backend/utils/core/voice_intent_classifier.py`, `frontend/static/js/voice-commands.js` |
| F14 | **Multimedia Artifact Preview** | Canvas-based image editor. Crop, resize, annotate, filter. Undo/redo. Integrates with artifact renderer. | `frontend/static/js/image-editor.js`, `frontend/static/css/image-editor.css` |

### Group G — Advanced

| # | Feature | Description | Key Files |
|---|---------|-------------|-----------|
| F10 | **Load Simulation & Benchmarking** | HTTP benchmarking, script profiling. Generates performance reports. Optional phase in pipeline. | `backend/utils/core/load_simulator.py`, `backend/agents/auto_agent_phases/performance_testing_phase.py` |
| F19 | **WebAssembly Sandbox** | Isolated test execution via wasmtime/wasmer. Fallback to subprocess. Memory limits. Auto-cleanup. | `backend/utils/core/wasm_sandbox.py` |

---

## Post-Generation Improvements

### 1. FinalReviewPhase with Interactive Git Push

The `FinalReviewPhase` now includes an **interactive Git decision gate**:

- After the standard code review, the phase checks for `git_push=True`, `repo_name`, and `git_token` in kwargs.
- If provided, it initializes a Git repository in the generated project, creates the initial commit, and pushes to the specified remote.
- Uses `gh` CLI (GitHub CLI) with automatic fallback to raw `git push`.
- Supports both GitHub and GitLab via the `ExportManager`.

**Usage (CLI):**
```bash
python auto_agent.py --description "My project" --name myproj \
    --git-push --repo-name myproj --git-token ghp_xxx --git-organization myorg
```

**Usage (Web UI):**
The project generation form includes optional fields for repository name and GitHub token. When provided, the project is automatically pushed after generation completes.

**Key files:** `backend/agents/auto_agent_phases/final_review_phase.py`

### 2. Autonomous Maintenance Task (Hourly)

A new `AutonomousMaintenanceTask` registers with APScheduler to run every 60 minutes:

1. **Code Analysis** &mdash; Uses `RefactoringAnalyzer` (or basic heuristics) to scan for code smells.
2. **Test Execution** &mdash; Runs `pytest` to verify project health.
3. **Auto-Repair** &mdash; If issues are found, applies automated fixes.
4. **Feature Branch** &mdash; Creates `auto-fix-{uuid}` branch for each cycle.
5. **PR Creation** &mdash; Opens a GitHub PR via `gh pr create` with a summary of changes.
6. **Feedback Recording** &mdash; Stores patterns in the `ErrorKnowledgeBase` for future reference.

**Registration:**
```python
from backend.utils.core.autonomous_maintenance import AutonomousMaintenanceTask

maintenance = AutonomousMaintenanceTask(
    project_root=project_root,
    agent_logger=logger,
    event_publisher=event_publisher,
    error_knowledge_base=error_kb,
)
maintenance.register(automation_manager)
```

**Key files:** `backend/utils/core/autonomous_maintenance.py`

### 3. PR and Continuous Improvement System

The `GitPRTool` provides a high-level interface for automated PR workflows:

- **Branch Management** &mdash; Create, switch, and list branches via `GitManager`.
- **Commit & Push** &mdash; Stage all changes, commit with a message, push to origin.
- **PR Creation** &mdash; Uses `gh pr create` with title, body, labels, and draft mode.
- **PR Listing & Merging** &mdash; List open PRs, merge with squash strategy.
- **Full Workflow** &mdash; `full_improvement_workflow()` chains: create branch → commit → push → create PR → return to base.

**Integration with FeedbackCycleManager:**
The maintenance cycle records its outcomes in the `ErrorKnowledgeBase`, allowing the system to learn from its own fixes and avoid repeating the same mistakes.

**Key files:** `backend/utils/core/git_pr_tool.py`, `backend/utils/core/git_manager.py`

---

## Architecture

```
                     ┌─────────────────┐
                     │   Entry Points  │
                     │  run_agent.py   │
                     │  run_web.py     │
                     │  auto_agent.py  │
                     └────────┬────────┘
                              │
               ┌──────────────┴──────────────┐
               │        AgentKernel          │
               │  Config · DI Containers     │
               └──────┬───────────┬──────────┘
                      │           │
          ┌───────────┴──┐  ┌────┴───────────┐
          │ DefaultAgent │  │   AutoAgent     │
          │ (CLI chat)   │  │ (18-phase       │
          │              │  │  pipeline)      │
          └──────┬───────┘  └────┬───────────┘
                 │               │
          ┌──────┴───────────────┴──────┐
          │    LLMClientManager         │
          │    (role-based model pool)  │
          └──────┬──────────────────────┘
                 │
          ┌──────┴──────────────────────┐
          │  Tool Registry              │
          │  @ollash_tool auto-discovery│
          └─────────────────────────────┘
```

### Agent Hierarchy

| Agent | Purpose |
|---|---|
| **CoreAgent** | Abstract base with LLM management, logging, token tracking, event publishing |
| **DefaultAgent** | Interactive orchestrator: intent classification, specialist model routing, tool-calling loop (up to 30 iterations) |
| **AutoAgent** | Multi-phase project generation pipeline |
| **AutoBenchmarker** | Automated model performance benchmarking |

### AutoAgent Pipeline

The AutoAgent runs projects through 18+ specialized phases:

| Phase | Description |
|---|---|
| Project Analysis | Analyze requirements and existing code |
| README Generation | Create project documentation |
| Structure Generation | Design directory and file layout |
| Structure Pre-Review | Validate proposed structure |
| Logic Planning | Plan implementation strategy per file |
| File Content Generation | Generate source code (parallel, dependency-aware) |
| Content Completeness | Verify all files have meaningful content |
| Empty File Scaffolding | Fill any remaining stubs |
| File Refinement | Refine code quality |
| Dependency Reconciliation | Resolve cross-file dependencies |
| License Compliance | Check and add license headers |
| Code Quarantine | Isolate problematic code |
| Iterative Improvement | Loop: suggest improvements, plan, implement |
| Test Generation & Execution | Generate and run tests with retry on failure |
| Exhaustive Review & Repair | Deep review, coherence scoring, targeted fixes |
| Senior Review | Multi-attempt review with fallback refinement |
| Verification | Final verification pass |
| Final Review | Generate project review + Git decision gate |
| Refactoring Phase *(F3)* | SOLID analysis and automatic refactoring |
| Infrastructure Generation *(F6)* | Terraform/K8s/Docker IaC |
| Documentation Translation *(F18)* | Multilingual README generation |
| Performance Testing *(F10)* | Load simulation and benchmarking |
| UI Review *(F4)* | Multimodal UI/UX analysis |

### Tool Domains

Tools are auto-discovered via the `@ollash_tool` decorator and lazy-loaded on first use:

| Domain | Examples |
|---|---|
| **Code** | File analysis, code generation, refactoring |
| **Network** | Port scanning, DNS lookup, connectivity checks |
| **System** | Process management, disk usage, log analysis |
| **Cybersecurity** | Vulnerability scanning, security auditing |
| **Git** | Commit, diff, branch management, PR automation |
| **Multimedia** | Image generation (InvokeAI), OCR, image editing |
| **Planning** | Project planning, task decomposition |
| **Orchestration** | Multi-agent coordination |

---

## Project Structure

```
Ollash/
├── backend/
│   ├── agents/              # Agent implementations
│   │   ├── auto_agent_phases/   # 18+ AutoAgent phases
│   │   ├── mixins/              # Context summarizer, intent routing, tool loop
│   │   ├── core_agent.py        # Abstract base agent
│   │   ├── default_agent.py     # Interactive CLI agent
│   │   └── auto_agent.py        # Project generation agent
│   ├── core/                # Kernel, config, DI containers
│   ├── interfaces/          # Abstract interfaces (IAgentPhase, IModelProvider, etc.)
│   ├── services/            # LLMClientManager
│   └── utils/
│       ├── core/            # 80+ core utilities
│       │   ├── autonomous_maintenance.py   # Hourly maintenance task
│       │   ├── checkpoint_manager.py       # Phase checkpoint system
│       │   ├── cost_analyzer.py            # Model cost tracking
│       │   ├── episodic_memory.py          # Long-term agent memory
│       │   ├── export_manager.py           # Multi-target export
│       │   ├── git_pr_tool.py              # Automated PR workflows
│       │   ├── load_simulator.py           # Performance benchmarking
│       │   ├── multi_agent_orchestrator.py # Parallel generation
│       │   ├── pair_programming_session.py # Live coding sessions
│       │   ├── plugin_manager.py           # Plugin discovery/loading
│       │   ├── prompt_tuner.py             # RL-based prompt tuning
│       │   ├── refactoring_analyzer.py     # SOLID code analysis
│       │   ├── voice_intent_classifier.py  # Advanced voice commands
│       │   ├── vulnerability_scanner.py    # Security scanning
│       │   └── wasm_sandbox.py             # WebAssembly isolation
│       └── domains/         # Tools by domain (code, network, system, cyber, etc.)
├── frontend/
│   ├── blueprints/          # 22 Flask blueprints
│   │   ├── cicd_bp.py           # CI/CD auto-healing dashboard
│   │   ├── cost_bp.py           # Cost analysis endpoints
│   │   ├── export_bp.py         # Multi-purpose export
│   │   ├── knowledge_graph_bp.py # Graph visualizer API
│   │   └── pair_programming_bp.py # Live coding SSE
│   ├── services/            # Web services
│   ├── static/
│   │   ├── js/
│   │   │   ├── app.js               # Main SPA logic
│   │   │   ├── knowledge-graph.js   # vis.js graph renderer
│   │   │   ├── pair-programming.js  # Live coding client
│   │   │   ├── voice-commands.js    # Speech API integration
│   │   │   └── image-editor.js      # Canvas image editor
│   │   └── css/
│   │       ├── knowledge-graph.css
│   │       └── image-editor.css
│   └── templates/           # Jinja2 templates
├── plugins/                 # Third-party plugin directory
│   └── example_plugin/      # Sample plugin implementation
├── prompts/                 # Agent prompts by domain
│   ├── code/refactoring_agent.json
│   └── infrastructure/default_infra_agent.json
├── tests/                   # Unit and integration tests
├── run_agent.py             # CLI entry point
├── run_web.py               # Web UI entry point
├── auto_agent.py            # Project generation entry point
├── auto_benchmark.py        # Model benchmarking entry point
├── docker-compose.yml       # Container orchestration
└── Dockerfile               # Container image
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) running locally or on your network
- Recommended models: `ministral-3:8b` (generalist), `qwen3-coder:30b` (coder), `ministral-3:14b` (planner)

### Installation

```bash
git clone https://github.com/John1987vlc/Ollash.git
cd Ollash
python -m venv venv

# Windows
.\venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Configuration

```bash
cp .env.example .env
```

Edit `.env` to set your Ollama server URL and model assignments:

| Variable | Purpose | Default |
|---|---|---|
| `OLLAMA_URL` | Ollama server address | `http://localhost:11434` |
| `DEFAULT_MODEL` | Fallback model | `ministral-3:8b` |
| `LLM_MODELS_JSON` | Role-to-model mapping (planner, coder, reviewer, etc.) | See `.env.example` |
| `TOOL_SETTINGS_JSON` | Sandbox level, rate limits, iteration limits | See `.env.example` |
| `AGENT_FEATURES_JSON` | Knowledge graph, OCR, speech, artifacts | See `.env.example` |
| `INVOKE_UI_URL` | InvokeAI server for image generation | `http://localhost:9090` |

### Running

```bash
# Interactive CLI
python run_agent.py --chat

# Single instruction
python run_agent.py "analyze the security of my network"

# Auto-confirm mode (skip confirmation gates)
python run_agent.py --chat --auto

# Generate a complete project
python auto_agent.py --description "A REST API for managing a todo list" --name todo-api

# Generate with Git push
python auto_agent.py --description "My project" --name myproj \
    --git-push --repo-name myproj --git-token ghp_xxx

# Generate with IaC
python auto_agent.py --description "Microservice API" --name api --include-infra

# Generate with multilingual docs
python auto_agent.py --description "Dashboard app" --name dash --languages en,es,zh

# Web UI at http://localhost:5000
python run_web.py

# Benchmark models
python auto_benchmark.py
python auto_benchmark.py --models ministral-3:8b qwen3-coder:30b
```

---

## Image Generation (InvokeAI)

Ollash integrates with InvokeAI 6.10+ for image generation:

1. Install and start InvokeAI (`invokeai-web`, default port 9090)
2. Set `INVOKE_UI_URL` in `.env`
3. Supported workflows:
   - **text2img** &mdash; Generate images from text prompts
   - **img2img** &mdash; Transform existing images with style/content modifications
   - **Models** &mdash; FLUX, Stable Diffusion, Dreamshaper, Juggernaut XL

---

## Testing

```bash
# Run all tests (mocked Ollama, no live server needed)
pytest tests/ -v --timeout=120 --ignore=tests/test_ollama_integration.py

# Single test file
pytest tests/test_code_agent_integration.py

# Specific test
pytest tests/test_code_agent_integration.py::TestClassName::test_method_name

# Lint
ruff check backend/ frontend/ tests/

# Format check
ruff format backend/ frontend/ tests/ --check
```

Tests use mocked Ollama by default. Integration tests requiring a live Ollama server are in `tests/test_ollama_integration.py` and auto-skipped when Ollama is unavailable.

---

## Docker

```bash
# Build and run
docker-compose up --build

# Set OLLASH_OLLAMA_URL in .env for Docker networking
# e.g., OLLASH_OLLAMA_URL=http://host.docker.internal:11434
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community standards.

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.
