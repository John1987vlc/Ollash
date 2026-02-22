# GEMINI.md - Project Overview for Local IT Agent - Ollash

This document provides an overview of the `local-it-agent-ollash` project, intended to guide the Gemini CLI agent in understanding and interacting with the codebase.

## Project Overview

**Local IT Agent - Ollash** is an AI code and IT assistant built using Python and the Ollama language model. Its primary purpose is to assist software developers with various tasks, including code analysis, prototype generation, and web research, leveraging a "Tool Calling" approach to interact with system tools and APIs, with potential for broader IT operations.

**Key Features:**
*   **Interactive CLI chat** with tool-calling loop (up to 30 iterations)
*   **Web UI** (Flask) with real-time SSE streaming, agent type selection, project generation, and model benchmarking
*   **5 specialist agents**: orchestrator, code, network, system, cybersecurity — each with curated prompts and tools
*   **Auto Agent pipeline**: 8-phase project generation from a text description
*   **Model benchmarker**: compare Ollama models on autonomous generation tasks
*   **Smart loop detection**: embedding similarity (all-minilm) catches stuck agents
*   **Reasoning cache**: ChromaDB vector store reuses past error solutions (>95% similarity)
*   **Context management**: automatic summarization at 70% token capacity
*   **Lazy tool loading**: tools instantiate on first use, not at startup
*   **Confirmation gates**: state-modifying tools require user approval (bypassable with `--auto`)
*   **Hybrid model selection**: intent classification routes to the best model per turn

**Main Technologies:**
*   **Python 3:** Core programming language.
*   **Ollama:** Local large language model (LLM) serving platform.
*   **`qwen3-coder:30b`:** Specific LLM used by the agent for code-related tasks.
*   **`requests`:** Python library for making HTTP requests.
*   **`pytest`:** Python testing framework.
*   **Flask:** Web framework for the new UI.
*   **Server-Sent Events (SSE):** Used in the Flask UI for real-time log streaming.

**Architecture:**
The project is structured around a central `DefaultAgent` (orchestrator) that manages interaction and routes tasks to specialized agents. These agents utilize modular tool sets located in `src/utils/domains/`. The core logic for foundational services like file management, command execution, and memory management resides in `src/utils/core/`. A Flask web application in `src/web/` provides a UI with real-time monitoring and interaction.

## Building and Running

### Installation Steps

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/your-org/ollash.git
    cd ollash
    ```
2.  **Create and Activate a Python Virtual Environment:**
    ```bash
    python -m venv venv
    # On Windows:
    .\venv\Scripts\activate
    # On macOS/Linux:
    source venv/bin/activate
    ```
3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    ```
4.  **Configure the Environment:**
    Create a `.env` file by copying the example file:
    ```bash
    # On Windows:
    copy .env.example .env
    # On macOS/Linux:
    cp .env.example .env
    ```
    Open the `.env` file and modify the variables, especially `OLLAMA_URL`, to match your setup.

5.  **Configure Ollama:**
    Ensure [Ollama](https://ollama.ai/) is installed, running, and accessible at the URL specified in your `.env` file. Then, download the necessary models (e.g., `qwen3-coder:30b`):
    ```bash
    ollama pull qwen3-coder:30b
    ```

### Running the Core Agent

To start an interactive chat session with the Local IT Agent - Ollash agent:
```bash
python run_agent.py --chat
```

### Running the Flask Web UI

To run the Flask web application:
```bash
python run_web.py
```
Access the UI by opening your web browser and navigating to `http://localhost:5000/`.

### Running the Auto Agent for Project Generation

To generate a project using the Auto Agent:
```bash
python auto_agent.py "Create a task manager app with Flask and SQLite" --name task_manager --loops 1
```

### Running the Model Benchmarker

To run the model benchmarking process:
```bash
python auto_benchmark.py
```
Alternatively, use the "Benchmark" tab in the Web UI.

## Testing

To run the unit and integration tests for the project:
```bash
pytest tests/
```
To run linting:
```bash
ruff check src/ tests/
```

## Development Conventions

*   **Language:** Python 3.x
*   **Dependencies:** Managed via `requirements.txt` and `requirements-dev.txt`.
*   **Testing Framework:** `pytest`.
*   **Configuration:** All agent settings are managed via environment variables, loaded from a `.env` file. See `.env.example` for a template.
*   **Code Structure:** Organized around a central `DefaultAgent` and modular tool sets within `src/utils/domains/`. Core services are in `src/utils/core/`, and the Flask UI is in `src/web/`.

## Important Files and Directories

*   `.env.example`: Template for the main configuration file (`.env`).
*   `prompts/`: Contains agent prompts per domain.
*   `src/`: Contains all primary source code.
    *   `src/agents/`: Hosts the main `DefaultAgent`, `AutoAgent`, and `AutoBenchmarker`.
    *   `src/core/config.py`: The centralized configuration loader module.
    *   `src/utils/core/`: Contains core utility functions and services (e.g., `OllamaClient`, `FileManager`, `CommandExecutor`).
    *   `src/utils/domains/`: Contains all modular tool implementations, organized by domain (e.g., `code`, `network`, `auto_generation`).
    *   `src/web/`: Contains the Flask web application.
        *   `app.py`: Flask application factory.
        *   `blueprints/`: Contains Flask blueprints for different routes.
        *   `services/`: Contains services for the web UI (e.g., `chat_event_bridge`, `chat_session_manager`).
        *   `templates/`: HTML templates for the UI.
        *   `static/`: CSS and JS assets for the UI.
*   `tests/`: Unit and integration tests for the codebase.
*   `run_agent.py`: The main entry point for running the interactive CLI agent.
*   `run_web.py`: The entry point for running the Flask web UI.
*   `auto_agent.py`: Entry point for the automatic project generation pipeline.
*   `auto_benchmark.py`: Entry point for the model benchmarking process.
*   `requirements.txt`, `requirements-dev.txt`: Project dependencies.
*   `README.md`: Primary project documentation.
