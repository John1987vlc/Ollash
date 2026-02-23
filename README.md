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

## v1.5.0 — Agentic Auto Mode Improvements

Nine targeted enhancements that make the hourly automation cycle truly autonomous, safe, and differential:

| # | Enhancement | Description |
|---|---|---|
| E1 | **Incremental Differential Analysis** | Hash-based file tracking — only re-analyzes changed files each cycle (Phase 0.5) |
| E2 | **Auto Tech Stack Detection** | Parses `requirements.txt`, `package.json`, `pyproject.toml` etc. to inject framework-aware prompt hints |
| E3 | **Auto Quality Monitoring** | Test + linter gate after every improvement loop; auto-heal sub-loop (up to 3 attempts) before proceeding |
| E4 | **Risk-Based Prioritization** | VulnerabilityScanner results feed into improvement suggestions — critical CVEs fixed first |
| E5 | **Git Event Trigger** | Background daemon polls `git diff --numstat`; reschedules the next automation run immediately on external changes |
| E6 | **Execution History Persistence** | Full Pydantic-modelled execution history (last 50 runs) stored in `tasks.json`; previous errors surfaced at cycle start |
| E7 | **Dynamic Documentation** | Phase 7.5 auto-generates CHANGELOG.md, ROADMAP.md, and refreshes `## Last Auto-Update` in README after each cycle |
| E8 | **File Locking** | `LockedFileManager` replaces `FileManager` — per-path `threading.Lock` + `asyncio.Lock` prevent concurrent write corruption |
| E9 | **Sandbox Validation** | `SandboxValidator` runs syntax check (and optional Docker compile) before writing; invalid files saved as `.candidate` |

---

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

### v1.5.0 Agentic Auto Mode

*   **Differential Analysis (`E1`)**: `AnalysisStateManager` saves an MD5 snapshot after each run. Subsequent runs skip unchanged files — full re-analysis only when the cache is cold or the project changes significantly.
*   **Tech Stack Detection (`E2`)**: `TechStackDetector` inspects manifest files and injects framework-specific prompt hints (e.g. `"Flask 2.3 — use Blueprints, application factory"`).
*   **Quality Gate + Auto-Heal (`E3`)**: After every improvement iteration, `QualityGate` runs tests and linter. Up to 3 heal iterations attempt to fix failures before the pipeline continues.
*   **Risk-Based Improvement (`E4`)**: `VulnerabilityScanner` results are ranked and prepended to improvement suggestions so security issues are addressed first.
*   **Git Event Trigger (`E5`)**: `GitChangeTrigger` runs as a daemon thread. When a developer pushes externally, the next hourly run is rescheduled to execute immediately.
*   **Execution History (`E6`)**: `AutomationManager` persists the last 50 `ExecutionRecord` entries per task; the agent reads previous errors at startup for contextual continuity.
*   **Dynamic Documentation (`E7`)**: New `DynamicDocumentationPhase` (7.5) auto-generates CHANGELOG.md, ROADMAP.md, and updates the README after each cycle using low-temperature LLM prompts.
*   **Concurrency Safety (`E8`)**: `LockedFileManager` extends `FileManager` with per-path `threading.Lock` and `asyncio.Lock` so background automation threads and async agent phases never corrupt shared files.
*   **Sandbox Validation (`E9`)**: `SandboxValidator` runs a subprocess syntax check (and Docker compile for Python) before committing any generated file to disk; rejected content is saved as `.candidate` for review.

### v1.4.0 Surgical Integrity & YAML Refactor

*   **Prompt Architecture**: Decoupling of logic and language. All prompts are now in English YAML files for maximum SLM reasoning power.
*   **Auto-Healing Engine**: Implementation of `CodePatcher` for surgical insertion of missing functions during generation.
*   **Git Lifecycle 2.0**: Robust tag handling with force-push support and automatic branch deletion after merging.
*   **Language Manager**: Centralized service for input translation and standardization to English.

## 🤝 Contributing

Contributions are welcome! Please read `CONTRIBUTING.md` for details on our code of conduct and the process for submitting pull requests.

## 📄 License

MIT License
