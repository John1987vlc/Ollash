# <img src="Ollash.jpg" width="48" height="48" valign="middle"> Ollash - Local IT Agent

**Ollash** is an advanced AI-powered Code and IT Assistant designed to operate entirely on your local infrastructure using **Ollama**. It combines multiple specialized agents into a cohesive "Agent-per-Domain" architecture to handle everything from complex software development to network analysis and cybersecurity audits.

---

## 🚀 Key Features

### 🧠 Specialized Multi-Agent Swarm
Ollash doesn't rely on a single generic prompt. It employs a team of specialized agents coordinated by a central orchestrator:
*   **Architect Agent:** Designs project structures and identifies dependencies.
*   **Developer Agent:** Writes, refines, and patches code across multiple languages.
*   **DevOps Agent:** Manages CI/CD pipelines and infrastructure generation.
*   **Auditor Agent:** Performs security scans and code quality reviews.
*   **Security Agent:** Monitors for vulnerabilities and enforces safety policies.

### 🏗️ Auto-Agent Project Pipeline
Generate complete, production-ready projects from a single text description through a rigorous 8-phase pipeline:
1.  **Analysis & Planning:** Detailed requirement breakdown.
2.  **Structure Generation:** Scaffolding the entire project tree.
3.  **Logic Design:** Planning function-level logic before coding.
4.  **Content Generation:** Parallelized file content creation.
5.  **Iterative Refinement:** Multiple passes to improve code quality.
6.  **Verification:** Automated testing and syntax validation.
7.  **Security & Compliance:** Vulnerability scanning and license checks.
8.  **Final Review:** Senior-level holistic project audit.

### 🌐 Modern Web UI (SPA)
A rich, interactive Single Page Application built with Flask and Vanilla CSS:
*   **Real-time Chat:** Interactive terminal-like chat with tool-calling capabilities.
*   **Architecture Visualization:** Dynamic graphs of your project's structure.
*   **Intelligence Hub:** Explore the agent's Knowledge Base (RAG), Episodic Memory, and Learned Error Patterns.
*   **Time Machine:** Create and restore project checkpoints.
*   **Ops Center:** Monitor background jobs and automation triggers.
*   **Model Benchmarker:** Compare local LLM performance on standardized tasks.

### 🛠️ Advanced Infrastructure
*   **Smart RAG (ChromaDB):** Semantic search over project documentation.
*   **Self-Healing Loops:** Automatically detects and fixes errors during generation.
*   **Safe Sandbox:** Executes commands in a controlled environment with policy enforcement.
*   **Hybrid Model Routing:** Automatically selects the best model for each specific task (e.g., Qwen3-Coder for coding, Ministral for planning).

---

## 💻 CLI Usage Examples

Ollash provides a powerful CLI to interact with its multi-agent swarm and utility tools.

### 💬 Interactive Chat
Enter an interactive chat session with specialized agents:
```bash
# Start a chat session similar to gemini-cli
python ollash_cli.py chat
```

### 🛠️ Project Generation (Multi-Agent Swarm)
Kickstart a new project with parallel Developer Agents:
```bash
# Generate a modern dashboard with 5 parallel developer agents
python ollash_cli.py agent "Create a React dashboard with TailwindCSS and Chart.js" --name dashboard_pro --pool-size 5
```

### 🐝 Swarm Tasks
Invoke the swarm for quick data processing tasks:
```bash
# Summarize a large document and extract key tasks
python ollash_cli.py swarm "Summarize docs/api_specification.pdf and list required endpoints"
```

### 🛡️ Security Operations
Perform automated vulnerability scans:
```bash
# Scan a directory for common security issues
python ollash_cli.py security scan ./my_new_project
```

### 📊 Benchmarking & Testing
Test local models or generate test suites:
```bash
# Run the model benchmarking suite
python ollash_cli.py benchmark

# Generate unit tests for a Python project
python ollash_cli.py test-gen ./src/core_logic.py
```

### 📁 Git Management
Automate PR creation and management:
```bash
# Prepare a PR description from recent changes
python ollash_cli.py git pr prepare
```

---

## 🛠️ Technology Stack
*   **Backend:** Python 3.x, Flask, Dependency Injector.
*   **LLM Engine:** Ollama (Default: `qwen3-coder:30b` and `ministral-3:8b`).
*   **Vector DB:** ChromaDB (for long-term memory and RAG).
*   **Memory:** SQLite (for episodic logs and decision tracking).
*   **Frontend:** HTML5, Vanilla CSS, Modern JavaScript (SPA architecture).

---

## ⚡ Quick Start

### Prerequisites
1.  Install [Ollama](https://ollama.ai/).
2.  Pull the required models:
    ```bash
    ollama pull qwen3-coder:30b
    ollama pull ministral-3:8b
    ollama pull qwen3-embedding:4b
    ```

### Installation
1.  Clone the repository:
    ```bash
    git clone https://github.com/your-repo/ollash.git
    cd ollash
    ```
2.  Set up a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: .\venv\Scripts\activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Configure your environment:
    ```bash
    cp .env.example .env
    # Edit .env to set your OLLAMA_URL
    ```

### Execution
*   **Start the Web UI:** `python run_web.py`
*   **Start the CLI Agent:** `python ollash_cli.py --chat`
*   **Generate a Project:** `python backend/agents/auto_agent.py "Create a FastAPI app with SQLite and JWT"`

---

## 📂 Project Structure
```text
ollash/
├── backend/            # Core logic, agents, and utilities
│   ├── agents/         # specialized agent implementations
│   ├── config/         # JSON configurations and policies
│   ├── core/           # Kernel, containers, and loaders
│   └── utils/          # Domain-specific tools (git, code, net, etc.)
├── frontend/           # Web UI (Flask templates, static assets)
├── docs/               # Detailed documentation and status reports
├── prompts/            # System prompts for all agent roles
└── .ollash/            # Local data (ChromaDB, logs, checkpoints)
```

---

## ⚡ Optimizaciones para Modelos Pequeños (≤4B)

Ollash incluye infraestructura específica para que modelos pequeños (Qwen 2.5 3B, Ministral 3B, etc.) generen código de calidad sin saturar su ventana de contexto:

| Optimización | Descripción |
|---|---|
| **1. Micro-Planner** | `DeveloperAgent` descompone cada archivo en 3–7 pasos atómicos antes de generarlo. El rol `nano_planner` recibe un prompt mínimo y devuelve un JSON array de pasos ordenados. |
| **2. RAG de Firmas** | `PhaseContext.select_related_files(signatures_only=True)` extrae sólo cabeceras de funciones/clases (vía AST en Python, regex en JS/TS/Go/Rust) en lugar de enviar archivos completos como contexto. |
| **3. Progress Injection** | `PhaseContext.update_step_progress()` registra el avance en un dict `step_progress`. `BasePhase._format_progress_context()` formatea ese estado y puede concatenarse a cualquier system prompt. |
| **4. Chain of Thought (dual output)** | `LLMResponseParser.extract_thought_action()` parsea respuestas en formato `{"thought": ..., "action": ...}` o `<thought>...</thought><action>...</action>`, sin modificar los métodos existentes. |
| **5. Roles Nano** | 3 roles ultra-focalizados (`nano_planner`, `nano_coder`, `nano_reviewer`) definidos en `prompts/domains/auto_generation/nano_roles.yaml` y mapeados en `backend/config/llm_models.json`. Cada rol tiene un prompt de sistema de <5 líneas. |
| **6. Decision Blackboard** | `DecisionBlackboard` (SQLite WAL, `backend/utils/core/memory/`) persiste decisiones de diseño entre fases (`record_decision` / `format_for_prompt`). Se inyecta en `PhaseContext` y sobrevive al reinicio del proceso. |
| **6b. Rescue Planning** | Cuando una fase falla, `AutoAgent._request_rescue_plan()` pide al LLM un array de 3 `RescuePhase` que se insertan dinámicamente en el pipeline para recuperar el estado. |

---

## 🛡️ Security & Safety
Ollash is built with security in mind. It includes a **Policy Enforcer** that intercepts all system commands, a **Code Quarantine** for analyzing suspicious snippets, and a **Vulnerability Scanner** to ensure generated code follows best practices.

---

## 📜 License
This project is licensed under the MIT License - see the LICENSE file for details.
