# Ollash - Local IT Agent

**Ollash** is an advanced AI-powered IT assistant designed to run locally using Ollama. It orchestrates specialized agents to handle coding, system administration, cybersecurity, and network tasks autonomously.

## 🚀 Key Features

*   **Autonomous Project Generation**: From concept to full codebase (frontend, backend, tests) with self-reflection.
*   **Specialist Swarm**: 5 specialized agents (Orchestrator, Coder, SysAdmin, NetSec, Secretary) working in concert.
*   **Continuous Maintenance (New)**: Scheduled audits (1-24h) to keep projects bug-free and optimized autonomously.
*   **OLLASH.md Manifest (New)**: Persistent "Project Brain" that syncs state directly to `main` for seamless session resumes.
*   **DevOps Standards (New)**: 
    *   **Semantic Versioning**: Automatic tagging (v0.1.X) based on progress.
    *   **Conventional Commits**: Standardized history (feat, fix, chore, docs).
    *   **Automated CI/CD**: Automatic generation of GitHub Actions (`ci.yml`) for testing and linting.
*   **Infrastructure Automation (New)**: Auto-creation of GitHub repositories and milestone tagging.
*   **Enhanced Monitoring (New)**: Timed logs with Heartbeat system to ensure the agent is active during long reasoning tasks.
*   **Semantic Integrity**: Advanced JavaScript and Python validation with cross-file consistency checks.

## 🛠️ Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-org/ollash.git
    cd ollash
    ```

2.  **Install dependencies:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: .\venv\Scripts\activate
    make setup
    ```

3.  **Configure environment:**
    Copy `.env.example` to `.env` and set your `OLLAMA_URL`.

4.  **Run the application:**
    ```bash
    python run_web.py
    ```
    Access the UI at `http://localhost:5000`.

## 🧪 Testing

```bash
# Unit tests (parallel, fast)
make test-unit

# Integration tests
make test-integration

# E2E Playwright tests (requires running server)
make test-e2e

# Full suite
make test
```

## 📐 Architecture

Ollash uses a modular "Phase" architecture for its AutoAgent:
- **Phase 0.5: Project Analysis**: Technical stack and requirement gathering.
- **Phase 1.0: Vision (README)**: Drafting the project soul with the Secretary.
- **Phase 2.5: Tactical Planning**: Logic plans and Agile Backlog with Issue linking.
- **Phase 4.0: Sniper Execution**: Sequential micro-task implementation with CoT verification.
- **Phase 5.2: Semantic Optimization**: Cross-file DOM and functional coherence.
- **Phase 7.0: Continuous Maintenance**: Background audit loops and auto-improvement.

### v1.3.0 DevOps & Stability Refactor

*   **`OLLASH.md` Manifest**: Implementation of a high-priority sync loop that keeps the `main` branch updated with the latest project state.
*   **Secretary Agent**: A specialized `writer` agent that manages professional English communications, PR descriptions, and Conventional Commit messages.
*   **Robust JSON Parsing**: Improved parser with trailing-comma correction and aggressive heuristic recovery for Small Language Models.
*   **Validation Relaxing**: Python validator now ignores `import-error` during generation to allow for sequential building.

## 🤝 Contributing

Contributions are welcome! Please read `CONTRIBUTING.md` for details on our code of conduct and the process for submitting pull requests.

## 📄 License

MIT License
