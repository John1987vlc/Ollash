# Ollash - Enterprise Local IT Agent

![Ollash Logo](Ollash.jpg)

**Ollash** is an advanced, autonomous AI agent platform designed for local infrastructure management, code generation, and DevOps orchestration. It combines the power of local LLMs (Ollama) with a robust, modular frontend to deliver a secure and intelligent IT assistant.

## 🚀 Key Features

### 🛡️ Enterprise Governance & Resilience
- **Binary Guard:** Strict detection and skipping of binary files (images, audio, etc.) during code generation to prevent LLM corruption and save tokens.
- **Context Anchor:** Robust fallback planning that preserves the original project description intent even during LLM logic planning failures.
- **Resilience Monitor:** Real-time loop detection and contingency planning. Automatically detects stuck agents and proposes alternative execution paths.
- **RBAC Policies:** Granular permission matrix to control agent access to File System, Network, CLI, and Security tools.
- **WASM Sandbox:** Execute generated code in a secure, isolated WebAssembly environment before applying it to your project.

### ⚙️ Operations & Automation
- **Enterprise CLI:** A powerful command-line interface for terminal-based automation and CI/CD integration.
- **Operations Center:** Built-in Task Scheduler (Cron) for automating maintenance scripts.
- **Execution DAG Visualizer:** Preview complex multi-step plans as Directed Acyclic Graphs before execution.
- **Git Integration:** Full version control management directly from the UI (Status, Diff, Commit, Log).

### 🧠 Intelligence & Knowledge
- **Prompts v2 (SQLite + YAML Seed):** Prompts are versioned in SQLite for real-time editing via Prompt Studio, with YAML fallbacks for high reliability.
- **Knowledge Base with OCR:** Drag-and-drop ingestion of PDFs and Images with automatic text extraction.
- **Prompt Studio:** Real-time prompt engineering with integrated linter and security validation.
- **Model Health Routing:** Latency monitoring with automatic fallback strategies for high-availability LLM access.

### 📊 Analytics & Insights
- **Activity Reports:** Weekly productivity summaries (Lines of Code, Time Saved, Error Rates).
- **GPU/Hardware Monitor:** Real-time tracking of GPU load and memory usage to prevent OOM errors.

## 🛠️ Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-org/ollash.git
    cd ollash
    ```

2.  **Install Dependencies:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # or .\venv\Scripts\activate on Windows
    pip install -r requirements.txt
    playwright install  # For E2E testing
    ```

3.  **Run the Application:**
    - **Web UI:** `python run_web.py` - Full visual experience for monitoring and interaction.
    - **Enterprise CLI:** `python ollash_cli.py --help` - Command-line power for developers and automation.
    - Access the UI at `http://localhost:5000`.

Check the [CLI Reference Guide](docs/CLI_REFERENCE.md) for detailed documentation of all commands.

## 📂 Project Structure

```text
Ollash/
├── backend/          # Core logic, agents, and system utilities
├── frontend/         # Flask web application and UI assets
├── legacy/           # Relocated legacy scripts and wrappers
├── tests/            # Comprehensive test suite (unit, integration, e2e)
├── docs/             # Technical documentation and CLI reference
├── .ollash/          # Hidden directory for logs, DBs, and vector stores
├── plugins/          # Extensible plugin system for custom tools
├── .github/          # CI/CD workflows and GitHub templates
├── requirements.txt  # Project dependencies
├── run_web.py        # Main entry point for the Web UI
└── ollash_cli.py     # Main entry point for the Enterprise CLI
```

## 🧪 Testing

We use **Pytest** for backend logic and **Playwright** for frontend E2E tests.

```bash
# Run Unit Tests
pytest tests/unit

# Run E2E UI Tests
pytest tests/e2e
```

## 🤝 Contributing

Please see `CONTRIBUTING.md` for guidelines. We follow a strict feature-branch workflow with required PR reviews.

---
*Powered by Ollama & Python*
