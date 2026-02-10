# GEMINI.md - Project Overview for Local IT Agent - Ollash

This document provides an overview of the `local-it-agent-ollash` project, intended to guide the Gemini CLI agent in understanding and interacting with the codebase.

## Project Overview

**Local IT Agent - Ollash** is an AI code and IT assistant built using Python and the Ollama language model. Its primary purpose is to assist software developers with various tasks, including code analysis, prototype generation, and web research, leveraging a "Tool Calling" approach to interact with system tools and APIs, with potential for broader IT operations.

**Key Features:**
*   **Code Agent:** Analyzes, understands, and modifies code.
*   **Prototype Generator:** Aids in rapid creation of project skeletons and components.
*   **Web Investigator:** Performs web searches and extracts information.
*   **Tooling:** Includes functionalities for command execution, file management, code analysis, and Git integration, now modularized into specialized utility classes.
*   **Asynchronous Web UI (New):** A Flask application provides a web-based interface for interacting with the AutoAgent, allowing real-time monitoring of project generation, file browsing, and log streaming.

**Main Technologies:**
*   **Python 3:** Core programming language.
*   **Ollama:** Local large language model (LLM) serving platform.
*   **`qwen3-coder-next`:** Specific LLM used by the agent for code-related tasks.
*   **`requests`:** Python library for making HTTP requests.
*   **`pytest`:** Python testing framework.
*   **Flask:** Web framework for the new UI.
*   **Server-Sent Events (SSE):** Used in the Flask UI for real-time log streaming.

**Architecture:**
The project is structured around a central `CodeAgent` that orchestrates various modular tool sets located in `src/utils/`. The core logic resides in `src/core/`, and a command-line interface is provided in `src/cli/`. Specialized agents (like `generador_prototipos.py` and `investigador_web.py`) are integrated into this modular tool framework. A new `flask_auto_agent_ui` directory hosts a Flask application that provides a web interface for the `AutoAgent`, enabling asynchronous project creation with real-time feedback.

## Building and Running

### Installation Steps

1.  **Clone the Repository:**
    ```bash
    git clone <URL_DEL_REPOSITORIO>
    cd local-it-agent-ollash
    ```
2.  **Create and Activate a Python Virtual Environment (for Ollash Core):**
    ```bash
    python -m venv venv
    # On Windows:
    .\venv\Scripts\activate
    # On macOS/Linux:
    source venv/bin/activate
    ```
3.  **Install Core Dependencies:**
    ```bash
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    ```
4.  **Configure Ollama:**
    Ensure [Ollama](https://ollama.ai/) is installed and running. Then, download the `qwen3-coder-next` model:
    ```bash
    ollama pull qwen3-coder-next
    ```
    Model configuration can be reviewed and modified in `config/settings.json`.

### Running the Core Agent

To start an interactive chat session with the Local IT Agent - Ollash agent:
```bash
python run_agent.py --chat
```

### Building and Running the Flask UI (New)

1.  **Navigate to the Flask application directory:**
    ```bash
    cd flask_auto_agent_ui
    ```
2.  **Create and Activate a Python Virtual Environment (for Flask UI):**
    *(It is recommended to use a separate virtual environment for the Flask app to manage its specific dependencies.)*
    ```bash
    python -m venv flask_venv
    # On Windows:
    .\flask_venv\Scripts\activate
    # On macOS/Linux:
    source flask_venv/bin/activate
    ```
3.  **Install Flask UI Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Run the Flask Application:**
    ```bash
    python app.py
    ```
5.  **Access the UI:** Open your web browser and go to `http://127.0.0.1:5000/`.

## Testing

To run the unit tests for the project:
```bash
pytest
```
Additional integration tests may require an Ollama instance running.

## Development Conventions

*   **Language:** Python 3.x
*   **Dependencies:** Managed via `requirements.txt` and `requirements-dev.txt` (core), and `requirements.txt` within `flask_auto_agent_ui` (Flask app).
*   **Testing Framework:** `pytest`.
*   **Configuration:** Main agent settings are in `config/settings.json`. Flask app configuration is handled within `app.py`.
*   **Code Structure:** Organized around a central `CodeAgent` and modular tool sets within `src/utils/`. The Flask UI is in its own `flask_auto_agent_ui` directory.

## Important Files and Directories

*   `src/`: Contains all primary source code.
*   `src/agents/`: Hosts the main `CodeAgent` and `AutoAgent`.
*   `src/utils/`: Contains common utility functions and all modular tool implementations.
*   `config/settings.json`: Main configuration file for the agent.
*   `flask_auto_agent_ui/`: Contains the Flask web application for the AutoAgent UI.
    *   `app.py`: Flask application entry point.
    *   `templates/`: HTML templates for the UI.
    *   `static/`: CSS and JS assets for the UI.
    *   `requirements.txt`: Dependencies for the Flask UI.
*   `generated_projects/auto_agent_projects/`: Directory where projects generated by the `AutoAgent` are stored.
*   `logs/auto_agent.log`: Main log file for the `AutoAgent`.
*   `tests/`: Unit tests for the codebase.
*   `run_agent.py`: The main entry point for running the interactive agent.
*   `auto_agent.py`: Entry point for the automatic project generation pipeline.
*   `pyproject.toml`: Project metadata and build system configuration.
*   `requirements.txt`, `requirements-dev.txt`: Project dependencies.
*   `README.md`: Primary project documentation.
