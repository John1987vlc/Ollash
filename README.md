# Ollash - Local IT Agent

**Ollash** is an advanced AI-powered IT assistant designed to run locally using Ollama. It orchestrates specialized agents to handle coding, system administration, cybersecurity, and network tasks autonomously.

## 🚀 Key Features

*   **Autonomous Project Generation**: From concept to full codebase (frontend, backend, tests) with self-reflection.
*   **Specialist Swarm**: 5 specialized agents (Orchestrator, Coder, SysAdmin, NetSec, Reviewer) working in concert.
*   **Semantic Integrity**: Advanced JavaScript validation and logical consistency checks.
*   **Multimodal Interface**: Voice commands and OCR text extraction.
*   **Visual Intelligence**:
    *   **Brain View**: Explore decision history and knowledge graphs visually.
    *   **Time Machine**: Checkpoint timeline for project restoration.
    *   **Pair Programming**: Split-view editor with AI ghostwriter.
*   **Advanced Tooling**:
    *   **Floating Terminal**: Integrated Xterm.js console with autocomplete.
    *   **Visual Structure Editor**: Drag-and-drop project scaffolding.
    *   **Integrations Panel**: IFTTT-style automation triggers.

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

Run the full test suite:
```bash
pytest tests/
```

## 🏗️ Architecture

Ollash uses a modular "Phase" architecture for its AutoAgent, allowing for flexible pipelines:
- **Analysis & Planning**: Requirements gathering and architecture design.
- **Generation**: Parallel code generation with CoT (Chain of Thought) verification.
- **Refinement & Repair**: Recursive self-correction loops.
- **Optimization**: Cross-file semantic consistency checks.

## 🤝 Contributing

Contributions are welcome! Please read `CONTRIBUTING.md` for details on our code of conduct and the process for submitting pull requests.

## 📄 License

MIT License
