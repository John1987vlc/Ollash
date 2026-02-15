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
| Final Review | Generate project review document |

### Tool Domains

Tools are auto-discovered via the `@ollash_tool` decorator and lazy-loaded on first use:

| Domain | Examples |
|---|---|
| **Code** | File analysis, code generation, refactoring |
| **Network** | Port scanning, DNS lookup, connectivity checks |
| **System** | Process management, disk usage, log analysis |
| **Cybersecurity** | Vulnerability scanning, security auditing |
| **Git** | Commit, diff, branch management |
| **Multimedia** | Image generation (InvokeAI), OCR |
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
│       ├── core/            # FileManager, CommandExecutor, ToolRegistry, etc.
│       └── domains/         # Tools by domain (code, network, system, cyber, etc.)
├── frontend/
│   ├── blueprints/          # 17 Flask blueprints (chat, auto_agent, monitors, etc.)
│   ├── services/            # Web services
│   ├── static/              # CSS, JS, assets
│   └── templates/           # Jinja2 templates
├── prompts/                 # Agent prompts by domain (orchestrator, code, network, etc.)
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
