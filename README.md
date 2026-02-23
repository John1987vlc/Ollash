# Ollash - Local IT Agent

**Ollash** is an advanced AI-powered IT assistant designed to run locally using Ollama. It orchestrates specialized agents to handle coding, system administration, cybersecurity, and network tasks autonomously.

## 🚀 Key Features

*   **Autonomous Project Generation**: From concept to full codebase (frontend, backend, tests) with self-reflection and iterative validation.
*   **Specialist Swarm**: 5 specialized agents (Orchestrator, Coder, SysAdmin, NetSec, Secretary) working in concert.
*   **Centralized Prompt Management (New)**: All system and agent prompts are now managed in YAML files (`prompts/`), allowing for professional technical editing without touching Python code.
*   **Surgical Code Repair (New)**: Intelligent "Auto-heal" system that detects semantic integrity failures and injects missing logic using AST-aware tools.
*   **Specialized Documentation Agent (New)**: Separate AI personality for technical writing, ensuring high-quality `README.md` and documentation without code hallucinations.
*   **Continuous Maintenance**: Scheduled audits (1-24h) to keep projects bug-free and optimized autonomously.
*   **OLLASH.md Manifest**: Persistent "Project Brain" that syncs state directly to `main` for seamless session resumes.
*   **DevOps Standards**: 
    *   **Semantic Versioning**: Automatic tagging (v0.1.X) based on task completion.
    *   **Conventional Commits**: Standardized history (feat, fix, chore, docs).
    *   **Automated CI/CD**: Automatic generation of GitHub Actions (`ci.yml`) for testing and linting.
*   **Infrastructure Automation**: Auto-creation of GitHub repositories and milestone tagging with `gh` CLI integration.
*   **System Scripting Sandbox (New)**: Isolated Docker-based environment for the System Agent to develop, lint, and test Bash and PowerShell scripts safely.
*   **Enhanced Monitoring**: Timed logs with Heartbeat system to ensure the agent is active during long reasoning tasks.
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
    pip install -r requirements.txt
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
# Run all tests
pytest tests/

# Linting
ruff check src/
```

## 📐 Architecture

Ollash uses a modular "Phase" architecture for its AutoAgent:
- **Phase 0.5: Project Analysis**: Technical stack and requirement gathering.
- **Phase 1.0: Vision (README)**: Drafting the project soul with the Documentation Agent.
- **Phase 2.5: Tactical Planning**: Logic plans and Agile Backlog with Issue linking.
- **Phase 4.0: Sniper Execution**: Sequential micro-task implementation with CoT and Auto-Healing.
- **Phase 5.2: Semantic Optimization**: Cross-file DOM and functional coherence.
- **Phase 7.0: Continuous Maintenance**: Background audit loops and auto-improvement.

### v1.4.0 Surgical Integrity & YAML Refactor

*   **Prompt Architecture**: Decoupling of logic and language. All prompts are now in English YAML files for maximum SLM reasoning power.
*   **Auto-Healing Engine**: Implementation of `CodePatcher` for surgical insertion of missing functions during generation.
*   **Git Lifecycle 2.0**: Robust tag handling with force-push support and automatic branch deletion after merging.
*   **Language Manager**: Centralized service for input translation and standardization to English.

## 🤝 Contributing

Contributions are welcome! Please read `CONTRIBUTING.md` for details on our code of conduct and the process for submitting pull requests.

## 📄 License

MIT License
