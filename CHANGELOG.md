# Changelog - Ollash

## [1.1.0] - 2026-02-22 (Agile Refactor & SLM Optimization)

### 🏗️ Agile & Iterative Engine
- **Micro-task Backlog:** Migration from waterfall file generation to an Agile backlog of atomic tasks. The agent now decomposes projects into a `BACKLOG.json` before execution.
- **Iterative Execution Loop:** Sequential execution of micro-tasks with dedicated context injection for each step, preventing LLM context saturation.
- **Context Distillation:** AST-based code skeleton extraction (`ContextDistiller`) to reduce token usage by sending only class/method signatures of related files.

### 🧠 SLM Reliability & Performance
- **High-End Hardware Tuning:** Optimized defaults for high-end GPUs (RTX 5080/4090):
  - Context window increased to **16,384 tokens**.
  - Precision tuning: Temperature `0.1`, Repeat Penalty `1.15`.
- **Structural XML Prompting:** Rigid response format using `<thinking_process>` (Chain of Thought) and `<code_created>` tags to ensure reliable code extraction.
- **AST Self-Correction Loop:** 3-attempt iterative loop with native Python syntax validation. The agent now receives tracebacks and self-corrects code before saving.
- **Model Standardization:** Standardized on `qwen3-coder:30b` as the primary coding engine across all configurations.

### 📊 UX & Frontend
- **Real-time Kanban Board:** New Agile dashboard in the UI to monitor task states (Todo, In Progress, Done) via SSE events.
- **Progress Tracking:** Granular event system (`agent_board_update`) for real-time task movement visualization.
- **Improved Workspace:** Integrated new `auto_agent.html` view for better monitoring of autonomous projects.

### 🛡️ DevSecOps & CI/CD
- **Master Branch CI Alignment:** Updated GitHub Actions to correctly trigger on the `master` branch.
- **Test Suite Revamp:** Fixed multiple regression bugs in unit and integration tests related to Phase Context and API endpoint remapping.
- **Enhanced Validation:** Stricter validation rules for main entry-point files (minimum payload checks, hallucination detection).

## [1.0.0] - 2026-02-22 (Release)

### ✨ Major Architectural Improvements
- **Frontend Refactoring:** Migration to a modern, modular Vanilla JS architecture with clear separation of concerns (Modules, Core, Services).
- **Centralized Backend:** Unified Flask-based API for all agent interactions, system monitoring, and project management.
- **Agent Roles System:** Introduction of specialized personas:
  - **Analyst:** Information synthesis and risk assessment.
  - **Writer:** High-quality documentation and audience adaptation.
  - **Senior Reviewer:** Code quality gates and architectural oversight.
  - **Orchestrator:** Intelligent task decomposition and routing.
- **Centralized Prompt Management:** All agent prompts migrated from hardcoded Python strings to a structured YAML hierarchy in `/prompts/`, allowing for easier maintenance and tuning without code changes.

### 🛡️ DevSecOps & Stability
- **E2E Testing Suite:** Implementation of Playwright-based end-to-end tests covering Chat, Project Generation, and Wizard flows.
- **Self-Healing CI/CD:** Integrated `CICDHealer` and `VulnerabilityScanner` modules.
- **Resource Management:** New GPU-aware rate limiting and concurrent session management.
- **Security Audit:** Elimination of absolute machine paths and improved secret handling via `.env`.

### 🚀 Features & UX
- **Real-time SSE Streaming:** Enhanced feedback loop for agent actions and logs.
- **Knowledge Graph:** Automated extraction of entities and relationships from generated code.
- **Automatic Learning System:** Vector-based memory for error resolution and pattern recognition.
- **Modular Toolset:** Organized domain-specific tools (Cybersecurity, Network, System, Infrastructure).

### 🧹 Cleanup
- Archived legacy debug scripts.
- Optimized `requirements.txt` and `.env.example`.
- Pristine root directory structure.

---
**Ollash v1.0.0: The Autonomous IT & Development Assistant.**
