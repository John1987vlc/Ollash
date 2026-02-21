# CLAUDE.md - AI Development Guide for Ollash

This document defines the architectural rules and technical conventions for AI assistants (Claude, Cursor, Gemini) working on the Ollash repository.

## 🏗️ Architectural Structure

- **Frontend (Modular)**: Blueprint-based architecture in `frontend/blueprints/`. 
    - UI logic must use Jinja2 templates (`frontend/templates/`).
    - Assets (JS/CSS) must be scoped and isolated in `frontend/static/`.
- **Backend (Decoupled)**: Modular services in `backend/`.
    - `backend/core/`: Essential kernel, configuration loader, and type definitions. NO business logic.
    - `backend/utils/core/`: Foundation services (FileManager, CommandExecutor).
    - `backend/utils/domains/`: Domain-specific tools. Avoid creating "God Directories".
- **Tests (Mirrored)**: `tests/unit/` and `tests/integration/` MUST exactly mirror the `backend/` and `frontend/` directory structure.

## 💻 Technical Stack
- **Languages**: Python 3.10/3.11.
- **Frameworks**: Flask (Web), Jinja2 (Templates), Pytest (Testing).
- **Core Ops**: Ollama (LLM Provider), Docker & Docker Compose (Containerization).
- **Quality**: Ruff (Linter/Formatter), Flake8 (Style), Bandit (Security).

## 📏 Coding Conventions (Mandatory)

### Backend
- **Strict Typing**: All functions must have type hints. Use `typing` and Pydantic v2.
- **Dependency Injection**: Use the `dependency-injector` container in `backend/core/containers.py`.
- **Circular Imports**: Strictly forbidden. Use interfaces in `backend/interfaces/` to break cycles.
- **Logging**: Use `AgentLogger`. Never use `print()` for operational logs.

### Frontend
- **Modularity**: One template per page/component. Use Jinja2 `include` and `extends`.
- **Isolation**: Avoid global JavaScript pollution. Scope scripts to their specific blueprints/pages.

### Testing
- **Unit Tests**: MUST mock all I/O (filesystem, database, network, LLM APIs).
- **Integration Tests**: Only allowed in `tests/integration/`. 
- **Fixtures**: Use Pytest fixtures for reusable components (mocked clients, temp directories).
- **Markers**: Mark tests appropriately: `@pytest.mark.unit`, `@pytest.mark.integration`.

## 🛠️ Key Commands

```bash
# Development
python run_web.py                # Start Web UI
python run_agent.py --chat       # Start CLI Agent

# Quality & Testing
pytest tests/unit/               # Run Unit Tests
pytest tests/e2e/ -m e2e         # Run E2E Tests (Full UI flow)
pytest                           # Run all tests
ruff check . --fix               # Linting check & auto-fix
ruff format .                    # Format code
flake8 backend/ frontend/ tests/ # Style check (strict)
playwright install chromium      # Install E2E browsers

# Docker
docker-compose up --build        # Launch full stack
```

## 🛡️ Security
- Never commit `.env` files.
- All state-modifying tools (`write_file`, `run_command`) must support a confirmation gate.
- Use `CommandExecutor` sandbox levels for shell execution.
