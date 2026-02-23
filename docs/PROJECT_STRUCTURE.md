# Ollash - Project Structure

## Directory Map

- `/backend`: Core agent logic, tools, and services.
  - `/agents`: Specialized agent implementations (AutoAgent, Benchmarker, etc.).
  - `/core`: Kernel, DI containers, and configuration.
  - `/utils/core`: Common utilities (IO, LLM parsing, system).
  - `/utils/domains`: Modular toolsets (Code, Network, System, Cybersecurity).
- `/frontend`: Web UI (Flask).
  - `/blueprints`: Backend API routes.
  - `/static/js`: Frontend modules (SPA logic, Page specific scripts).
  - `/templates`: HTML layouts and page views.
- `/docs`: Technical documentation and references.
- `/prompts`: Centralized prompt repository (YAML/JSON).
- `/tests`: Comprehensive test suite (Unit, Integration, E2E).

## Key Components

1. **AutoAgent**: Orchestrates the 8-phase project generation pipeline.
2. **Specialist Swarm**: 5 domain-specific agents for targeted tasks.
3. **Sandbox**: Docker/WASM isolated execution environment.
4. **Benchmarker**: Comparative analysis of Ollama models.
5. **Prompt Studio**: IDE for live prompt editing and versioning.
