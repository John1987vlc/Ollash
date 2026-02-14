# Ollash - Local IT Agent

![Ollash Logo](Ollash.png)

Ollash is an advanced, locally-run AI agent framework for developers and IT professionals. It uses Ollama to power a suite of specialized agents that can perform tasks like code analysis, project generation, system monitoring, and more.

---

## 🚀 Key Features

*   **Interactive CLI:** A powerful chat-based interface for interacting with the agent.
*   **Autonomous Project Generation:** An `AutoAgent` that can generate complete software projects from a natural language description.
*   **Web UI:** A Flask-based web interface for chatting with agents, generating projects, and monitoring the system.
*   **Specialized Agents:** A suite of specialized agents for different domains, including code, network, system, and cybersecurity.
*   **Knowledge Workspace:** A dynamic knowledge base that allows the agent to learn from documents and past interactions.
*   **Proactive Automation:** A system for scheduling tasks, monitoring system resources, and sending real-time alerts.
*   **Image Generation:** Fully integrated image generation with InvokeAI 6.10+ supporting text-to-image (text2img) and image-to-image (img2img) transformations with support for multiple models (FLUX, Stable Diffusion, Dreamshaper, Juggernaut XL).

---

## 🏗️ Architecture

Ollash is built on a modular and extensible architecture. The project is logically split into `backend/` for core Python logic (agents, core services, utilities) and `frontend/` for the Flask web application. Core functionalities are provided by a set of specialized services, such as the `LLMClientManager`, `ToolExecutorService`, and `MemoryService`. The system's behavior is controlled by a set of configuration files, allowing for easy customization.

For a more detailed overview of the architecture, please refer to the [Architecture Documentation](docs/Haiku/ARCHITECTURE_DIAGRAM.md).

## 📁 Project Structure

The project follows a well-organized directory structure to separate concerns and improve maintainability:

*   **`backend/`**: Contains all Python backend source code, including agent implementations, core utilities, services, and interfaces. This is the new home for the core logic previously found in `src/`.
*   **`frontend/`**: Houses the Flask web application, including `app.py`, blueprints, services, static assets, and HTML templates.
*   **`docs/`**: Documentation files such as `GEMINI.md`, `CLAUDE.md`, and `DEPLOYMENT_STATUS.md`.
*   **`prompts/`**: Stores JSON configuration for agent prompts by domain.
*   **`tests/`**: Contains all unit and integration tests for the project.
*   **`reports/`**: Stores test results and other generated reports.
*   **`scripts/`**: Utility and debugging scripts.
*   **`.ollash/`**: Configuration and memory files specific to the agent's runtime, such as `.agent_memory.json` and ChromaDB data.
*   **`requirements.txt`**, **`requirements-dev.txt`**: Python dependency lists.
*   **`.env.example`**: Template for environment variables.
*   **`run_agent.py`**, **`run_web.py`**, **`auto_agent.py`**, **`auto_benchmark.py`**: Main entry points for the application.

---

## 🎯 Getting Started

### Prerequisites
- Python 3.8+
- Ollama (for local LLM inference)
- An Ollama instance running (default `http://localhost:11434`)
- Required models for Ollama. You can find the list of models in the `GEMINI.md` file.

### Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/John1987vlc/Ollash.git
    cd Ollash
    ```
2.  **Create a Python Virtual Environment:**
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

### Configuration

1.  Copy the example environment file:
    ```bash
    cp .env.example .env
    ```
2.  Edit the `.env` file to set your Ollama server address and other configurations:
    ```bash
    OLLASH_OLLAMA_URL=http://localhost:11434
    INVOKE_UI_URL=http://127.0.0.1:9090
    ```

### Image Generation Setup (InvokeAI 6.10+)

For image generation features, ensure InvokeAI 6.10+ is installed and running:
1. **InvokeAI Installation:**
   ```bash
   pip install invokeai
   invokeai-web  # Start the InvokeAI server (default: http://localhost:9090)
   ```
2. **Configure the INVOKE_UI_URL** in your `.env` file to match your InvokeAI server address.
3. **Supported Features:**
   - **Text-to-Image (text2img):** Generate images from text prompts
   - **Image-to-Image (img2img):** Transform existing images with style/content modifications
   - **Multiple Models:** FLUX, Stable Diffusion, Dreamshaper, Juggernaut XL, and more

### Running the Application

*   **Interactive CLI:**
    ```bash
    python run_agent.py --chat
    ```
*   **Web UI:**
    ```bash
    python run_web.py
    ```
    Access the web UI at `http://localhost:5000`.

*   **Autonomous Project Generation:**
    ```bash
    python auto_agent.py --description "Create a simple Python Flask web application for a to-do list." --name "my-todo-app"
    ```

### Testing

To run the complete test suite:
```bash
pytest
```

To run linting checks:
```bash
ruff check backend/ frontend/ tests/
```
