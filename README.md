# Ollash

![Ollash Logo](Ollash.png)

[![CI/CD Pipeline](https://github.com/John1987vlc/Ollash/actions/workflows/ci.yml/badge.svg)](https://github.com/John1987vlc/Ollash/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Ollama Powered](https://img.shields.io/badge/powered%20by-Ollama-blueviolet)](https://ollama.com)

**Ollash** is a modular AI agent framework powered by [Ollama](https://ollama.com) for local IT tasks: code analysis, network diagnostics, system administration, cybersecurity, and autonomous project generation. It orchestrates specialized agents through Ollama's tool-calling API, keeping all inference local and private.

---

## Key Features

- **Interactive CLI** &mdash; Chat-based interface with intent classification, automatic agent-type selection, and semantic loop detection.
- **Autonomous Project Generation (AutoAgent)** &mdash; Generate complete software projects from natural language descriptions using a multi-phase pipeline with 22+ specialized phases.
- **Web UI** &mdash; Flask-based dashboard for chatting with agents, generating projects, cloning Git repositories, monitoring the system, managing automations, and viewing artifacts.
- **Specialized Agents** &mdash; Domain agents for code, network, system, cybersecurity, and orchestration, each with curated prompts and tool sets.
- **Knowledge Workspace** &mdash; ChromaDB-backed RAG context selection, knowledge graph building, cross-reference analysis, and decision memory.
- **Proactive Automation** &mdash; Trigger-based automation with scheduling (APScheduler), real-time alerts, webhook notifications (Slack, Discord, Teams), and system monitoring.
- **Image Generation** &mdash; InvokeAI 6.10+ integration supporting text-to-image and image-to-image with FLUX, Stable Diffusion, Dreamshaper, and Juggernaut XL models.
- **Model Benchmarking** &mdash; Benchmark LLM models with multidimensional rubrics, dynamic model routing via affinity matrix, visual performance analytics (Chart.js), and AI-generated intelligence reports.
- **Dependency Injection** &mdash; Full DI via `dependency-injector` for testable, modular architecture.

---

## 20+ Major Feature Improvements

### Group A — Foundation

| # | Feature | Description | Key Files |
|---|---------|-------------|-----------|
| F2 | **Checkpoint & Resume** | JSON per-project + SQLite index. Save/restore AutoAgent pipeline state after each phase. | `backend/utils/core/checkpoint_manager.py` |
| F16 | **Plugin System** | Third-party extensions via `OllashPlugin` ABC. Auto-discovery in `plugins/` directory. | `backend/utils/core/plugin_manager.py` |
| F21 | **Centralized JSON Config** | Migrated from large `.env` strings to modular JSON files in `backend/config/`. Supports dynamic reloading. | `backend/core/config.py`, `backend/config/*.json` |

### Group B — Core Agents & Intelligence

| # | Feature | Description | Key Files |
|---|---------|-------------|-----------|
| F19 | **Anti-Looping & Action Logic** | Strict planning repetition counters and loop bypass for legitimate plan refinements. Forces "Action over Planning". | `backend/agents/mixins/tool_loop_mixin.py`, `backend/utils/core/loop_detector.py` |
| F24 | **Aggressive Context Mgmt** | Recursive summarization triggered at 70% capacity (2048 token limit optimized for speed and reliability). | `backend/agents/mixins/context_summarizer_mixin.py` |
| F25 | **Intelligent Intent Routing** | Automatic specialist selection: routes prototyping and development requests to the `coder` model role. | `backend/agents/mixins/intent_routing_mixin.py` |

### Group C — Performance & Benchmarking

| # | Feature | Description | Key Files |
|---|---------|-------------|-----------|
| F14 | **AI Intelligence Reports** | Automatic LLM-generated executive summaries after benchmarks comparing performance, speed, and reliability. | `backend/agents/auto_benchmarker.py`, `frontend/blueprints/benchmark_bp.py` |
| F26 | **Visual Analytics Dashboard** | Real-time performance charts (Chart.js) comparing Tokens per Second vs. Success Rate across models. | `frontend/static/js/app.js`, `frontend/static/css/style.css` |
| F13 | **Auto-RAM Management** | Explicit model unloading via `keep_alive: 0` after tasks to ensure maximum resources for subsequent models. | `backend/utils/core/ollama_client.py` |

### Group D — System Health (Windows Optimized)

| # | Feature | Description | Key Files |
|---|---------|-------------|-----------|
| F22 | **Windows Health Metrics** | Real-time CPU, RAM, Disk (Auto-Drive detection), and Network I/O monitoring optimized for Win32 systems. | `frontend/blueprints/system_health_bp.py` |
| F23 | **Network Auto-Scaling** | Dynamic unit scaling (MB/GB) and 2-decimal precision for Upload/Download traffic reporting. | `frontend/static/js/app.js` |
| F27 | **Smart Prompt Library** | Integrated library of specialized IT prompts (System, Network, Security, Code) with one-click agent assignment. | `frontend/static/js/app.js` |

### Group E — Robustness & Architecture

| # | Feature | Description | Key Files |
|---|---------|-------------|-----------|
| F29 | **Recursive Depth Limits** | Prevent "folder-maze" over-engineering by limiting project structure generation to a manageable depth (default: 2). | `backend/utils/domains/auto_generation/structure_generator.py` |
| F30 | **Logic Plan Capping** | Limit file planning to top 10 files per category to prevent LLM timeouts and logic fragmentation. | `backend/agents/auto_agent_phases/logic_planning_phase.py` |
| F18 | **Sanitized Chat Logging** | Human-readable console logs with "Thinking" indicators; raw Ollama data and large embeddings kept in file logs only. | `backend/utils/core/agent_logger.py`, `backend/utils/core/structured_logger.py` |

### Group F — Modern IDE & Visualization

| # | Feature | Description | Key Files |
|---|---------|-------------|-----------|
| F31 | **Multi-Tab IDE Interface** | Professional IDE with multi-tab Monaco editor support, dirty-state indicators, and persistent state syncing. | `frontend/static/js/app.js` |
| F32 | **Mermaid.js Flowcharts** | Real-time rendering of technical diagrams and flowcharts directly within chat bubbles using Mermaid syntax. | `frontend/templates/index.html` |
| F33 | **Advanced File Ops** | Context-aware project management: rename, delete, and save files with built-in security traversal protection. | `frontend/blueprints/auto_agent_bp.py` |
| F34 | **Health Mini-Charts** | Sparkline trend-lines in the sidebar for real-time visual tracking of CPU/RAM performance history. | `frontend/static/js/app.js`, `frontend/static/css/style.css` |
| F35 | **Strict Logic Validation** | Enhanced LLM code generation with regex-based export verification and automated skeleton detection. | `backend/utils/domains/auto_generation/enhanced_file_content_generator.py` |
| F36 | **Secure Git Integration** | Seamless GitHub integration with PAT support and branch management. View PR history directly in the UI. | `frontend/blueprints/auto_agent_bp.py`, `backend/utils/core/git_pr_tool.py` |
| F37 | **Continuous Auto-Review** | Scheduled hourly maintenance tasks that analyze code, run tests, and generate automated PRs for improvements. | `backend/utils/core/autonomous_maintenance.py`, `backend/utils/core/task_scheduler.py` |

### Group G — Advanced UI Features

| # | Feature | Description | Key Files |
|---|---------|-------------|-----------|
| F38 | **Documentation Center** | Integrated documentation viewer with Markdown rendering and sidebar navigation. | `frontend/templates/index.html`, `frontend/static/js/app.js` |
| F39 | **Costs Dashboard** | Real-time dashboard tracking token usage, estimated costs, and efficiency metrics with charts. | `frontend/blueprints/cost_bp.py`, `frontend/static/js/app.js` |
| F40 | **Architecture Graph** | Interactive visualization of project components and dependencies using vis.js. | `frontend/blueprints/knowledge_graph_bp.py`, `frontend/static/js/app.js` |
| F41 | **Voice Input** | Browser-based speech recognition for voice commands and dictation directly into the chat. | `frontend/static/js/app.js`, `frontend/static/css/style.css` |
| F42 | **Pair Programming Mode** | Split-screen layout allowing side-by-side chat and project workspace interaction. | `frontend/static/css/style.css`, `frontend/static/js/app.js` |

### Group H — Phase 5 & Advanced UI Integration

| # | Feature | Description | Key Files |
|---|---------|-------------|-----------|
| F43 | **Multimodal Interface** | Full support for Drag & Drop and file attachments (Images/PDFs) in the chat. Real-time thumbnail previews and backend ingestion. | `frontend/blueprints/multimodal_bp.py`, `frontend/static/js/app.js` |
| F44 | **WASM/Docker Sandbox** | Isolated execution environment for Python/JS code blocks with an integrated console in the code viewer. | `frontend/blueprints/sandbox_bp.py`, `backend/utils/core/wasm_sandbox.py` |
| F45 | **Executive Reports** | One-click generation of technical executive summaries with static, predictable download URLs. | `frontend/blueprints/export_bp.py`, `backend/utils/core/activity_report_generator.py` |
| F46 | **AI Image Studio** | Interactive Canvas-based editor for AI-generated images. Supports manual tweaks and img2img variation requests. | `frontend/static/js/image-editor.js`, `backend/utils/domains/image_generation_tools.py` |
| F47 | **Agent Memory (Brain)** | Visual knowledge base browser. View learned patterns and manually "unlearn" incorrect agent logic. | `frontend/blueprints/learning_bp.py`, `backend/utils/core/automatic_learning.py` |
| F48 | **Webhook Ecosystem** | Enterprise-grade notifications for Slack, Discord, and Teams with customizable event subscriptions. | `frontend/blueprints/webhooks_bp.py`, `backend/utils/core/webhook_manager.py` |
| F49 | **Coworking Mode** | Multi-agent chat sessions with distinct visual identities and specialized routing between agent types. | `frontend/static/js/app.js`, `backend/utils/domains/bonus/cowork_impl.py` |
| F50 | **Real-time Benchmark** | Modal-based model comparison. Benchmarking multiple Ollama models simultaneously with live metrics. | `frontend/blueprints/benchmark_bp.py`, `frontend/templates/index.html` |

---

## 6 Integrated Pipeline Features

### Feature 1: Template-First Generation
AutoAgent now prioritizes project templates (React, FastAPI, Automation) as foundations before LLM refinement, ensuring industry-standard layouts from the first iteration.

### Feature 2: Floating Terminal & Wizards
Interactive project creation wizard and a VS-Code style floating terminal for real-time command execution and feedback.

### Feature 3: Senior Review as Pull Request
Enhanced Senior Review phase that can open a GitHub PR with review findings and post file-specific issues as PR comments.

### Feature 4: Security Scan Phase
Runs `VulnerabilityScanner` on all files, produces `SECURITY_SCAN_REPORT.md`, and optionally blocks the pipeline on critical findings.

### Feature 5: Multi-Turn Metrics
Real-time tracking of Duration and Token count per individual chat response, with a "Details" modal for deep iteration breakdown.

### Feature 6: Clone from Git (Web UI)
Clone existing Git repositories directly from the Web UI with automatic project integration.

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
               │  Config (JSON) · DI Containers│
               └──────┬───────────┬──────────┘
                      │           │
          ┌───────────┴──┐  ┌────┴───────────┐
          │ DefaultAgent │  │   AutoAgent     │
          │ (Action-Oriented)│ (22-phase      │
          │              │  │  pipeline)      │
          └──────┬───────┘  └────┬───────────┘
                 │               │
          ┌──────┴───────────────┴──────┐
          │    LLMClientManager         │
          │    (Routing + Rate Limits)  │
          └──────┬──────────────────────┘
                 │
          ┌──────┴──────────────────────┐
          │  Tool Registry              │
          │  @ollash_tool auto-discovery│
          └─────────────────────────────┘
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

Edit `backend/config/*.json` to set your Ollama server URL and model assignments. The system now loads these automatically at startup.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Security

See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.
