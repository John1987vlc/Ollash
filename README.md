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
*   **Image Generation:** An integrated tool for generating images using Invoke AI.

---

## 🏗️ Architecture

Ollash is built on a modular and extensible architecture that makes it easy to add new agents, tools, and features. Core functionalities are provided by a set of specialized services, such as the `LLMClientManager`, `ToolExecutorService`, and `MemoryService`. The system's behavior is controlled by a set of configuration files, allowing for easy customization.

For a more detailed overview of the architecture, please refer to the [Architecture Documentation](docs/Haiku/ARCHITECTURE_DIAGRAM.md).

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

To run the test suite and verify the installation:
```bash
pytest
```

---

## 🤝 Contributing

We welcome contributions to Ollash! Please see our [Contributing Guide](CONTRIBUTING.md) for more details on how to get started.

---

## 📜 License

Ollash is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
