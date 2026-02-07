# GEMINI.md - Project Overview for Gemini CLI

This document provides an overview of the `local-it-agent-ollash` project, intended to guide the Gemini CLI agent in understanding and interacting with the codebase.

## Project Overview

**Local IT Agent - Ollash** is an AI code and IT assistant built using Python and the Ollama language model. Its primary purpose is to assist software developers with various tasks, including code analysis, prototype generation, and web research, leveraging a "Tool Calling" approach to interact with system tools and APIs, with potential for broader IT operations.

**Key Features:**
*   **Code Agent:** Analyzes, understands, and modifies code.
*   **Prototype Generator:** Aids in rapid creation of project skeletons and components.
*   **Web Investigator:** Performs web searches and extracts information.
*   **Tooling:** Includes functionalities for command execution, file management, code analysis, and Git integration, now modularized into specialized utility classes.

**Main Technologies:**
*   **Python 3:** Core programming language.
*   **Ollama:** Local large language model (LLM) serving platform.
*   **`qwen3-coder-next`:** Specific LLM used by the agent for code-related tasks.
*   **`requests`:** Python library for making HTTP requests.
*   **`pytest`:** Python testing framework.

**Architecture:**
The project is structured around a central `CodeAgent` that orchestrates various modular tool sets located in `src/utils/`. The core logic resides in `src/core/`, and a command-line interface is provided in `src/cli/`. Specialized agents (like `generador_prototipos.py` and `investigador_web.py`) will be refactored or integrated into this modular tool framework.

## Building and Running

### Installation Steps

1.  **Clone the Repository:**
    ```bash
    git clone <URL_DEL_REPOSITO>
    cd local-it-agent-ollash
    ```
2.  **Create and Activate a Python Virtual Environment:**
    ```bash
    python -m venv venv
    # On Windows:
    .\venv\Scripts\activate
    # On macOS/Linux:
    source venv/bin/activate
    ```
3.  **Instala las Dependencias:**
    ```bash
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    ```
4.  **Configura Ollama:**
    Asegúrate de tener [Ollama](https://ollama.ai/) instalado y en funcionamiento. Luego, descarga el modelo `qwen3-coder-next`:
    ```bash
    ollama pull qwen3-coder-next
    ```
    Model configuration can be reviewed and modified in `config/settings.json`.

### Running the Agent

To start an interactive chat session with the Local IT Agent - Ollash agent:
```bash
python run_agent.py --chat
```

## Testing

To run the unit tests for the project:
```bash
pytest
```

## Development Conventions

*   **Language:** Python 3.x
*   **Dependencies:** Managed via `requirements.txt` and `requirements-dev.txt`.
*   **Testing Framework:** `pytest`.
*   **Configuration:** Main agent settings are in `config/settings.json`.
*   **Code Structure:** Organized around a central `CodeAgent` and modular tool sets within `src/utils/`.

## Important Files and Directories

*   `src/`: Contains all primary source code.
*   `src/agents/`: Hosts the main `CodeAgent`.
*   `src/utils/`: Contains common utility functions and all modular tool implementations.
*   `config/settings.json`: Main configuration file for the agent.
*   `tests/`: Unit tests for the codebase.
*   `run_agent.py`: The main entry point for running the agent.
*   `pyproject.toml`: Project metadata and build system configuration.
*   `requirements.txt`, `requirements-dev.txt`: Project dependencies.
*   `README.md`: Primary project documentation.
