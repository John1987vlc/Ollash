# Changelog - Ollash

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
