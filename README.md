# 🤖 Ollash

### **The Local Autonomous IT & Code Assistant Framework**

[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)]()
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Support](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

**Ollash** is a next-generation, local-first autonomous agent framework designed to bridge the gap between Large Language Models and real-world IT operations. Powered by **Ollama**, Ollash provides a highly modular ecosystem for code analysis, system administration, and automated project generation—all while keeping your data strictly on your machine.

---

## 🚀 Key Features

### 🧠 **Advanced Cognitive Engine**
- **Centralized Prompt Management:** (New in v1.0.0) All agent personas and task templates are managed via a structured YAML hierarchy in `/prompts/`, enabling rapid tuning and multi-language support without code changes.
- **Episodic Memory:** Persistent reasoning cache using ChromaDB to reuse solutions for recurring errors.
- **Hybrid Model Routing:** Automatically selects the best model (e.g., `qwen3-coder-next`) based on intent classification.
- **Smart Context Management:** Automatic summarization and token pressure relief at 70% capacity.

### 🛡️ **Domain-Specific Specialists**
- **Architect & Planner:** High-level solution design and dependency mapping.
- **Code Expert:** Deep repository analysis, refactoring, and test generation.
- **Cybersecurity:** Vulnerability scanning, dependency auditing, and security policy enforcement.
- **Network & Systems:** Real-time diagnostics, Nmap integration, and system monitoring.
- **Senior Reviewer:** (New in v1.0.0) Automated quality gates and architectural compliance checks.
- **Orchestrator:** High-level task decomposition and multi-agent coordination.

### 🌐 **Full-Stack Experience**
- **Modern Web UI:** Flask-based interface with real-time **Server-Sent Events (SSE)** for transparent agent thought-streaming.
- **Interactive CLI:** A robust terminal interface for quick tasks and direct chat.
- **Auto-Agent Pipeline:** 8-phase autonomous project generation from a single text prompt.

---

## 🏗️ Architecture

Ollash follows a strict **Separation of Concerns (SoC)**:

- **`frontend/`**: Modular Jinja2 templates, Blueprint-based routing, and isolated JS/CSS components.
- **`backend/`**: 
    - `agents/`: Core logic for specialized behaviors.
    - `services/`: LLM management and multi-provider abstraction.
    - `utils/domains/`: Decoupled toolsets (Network, Code, System).
    - `core/`: Foundation services (Config, Kernel, Type definitions).

---

## 🛠️ Quick Start

### **Option A: Docker (Recommended)**
The fastest way to get started with Ollash and its dependencies.
```bash
docker-compose up --build
```
*Access the Web UI at `http://localhost:5000`*

### **Option B: Local Installation**
1. **Requirements:** Python 3.10+ and [Ollama](https://ollama.ai/) running.
2. **Setup:**
   ```bash
   git clone https://github.com/your-org/ollash.git && cd ollash
   python -m venv venv
   source venv/bin/activate  # venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```
3. **Run:**
   ```bash
   # Start Web UI
   python run_web.py
   
   # Start CLI Agent
   python run_agent.py --chat
   ```

---

## 🧪 Testing & Quality Assurance

Ollash employs a multi-layered testing strategy to ensure the stability of both agent logic and the user interface.

### ⚙️ Testing Prerequisites
Install development dependencies and browser binaries:
```bash
pip install -r requirements-dev.txt
playwright install chromium
```

### 🏃 Running Tests
Tests are categorized by speed and scope:

- **Unit Tests (Logic & Backend):** Fast, with full mocking of I/O and LLMs.
  ```bash
  pytest tests/unit/
  ```
- **E2E Tests (User Interface):** Real browser tests with Playwright. Automatically detects JS console errors.
  ```bash
  pytest tests/e2e/ -m e2e
  ```
- **Full Validation:**
  ```bash
  pytest
  ```

### 🛡️ Quality Standards
- **Zero-Warning Policy:** The CI/CD pipeline is configured to treat any deprecation warnings or linting errors as failures.
- **JavaScript Guardian:** E2E tests fail if a `console.error` is detected in the browser, ensuring a bug-free UI.

---

## 🤝 Contributing

We welcome contributions! Please see our [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details on our code of conduct and the process for submitting pull requests.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---
*Built with ❤️ for the Open Source Community.*
