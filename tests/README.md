# tests — Test Suite

1106+ unit tests, integration tests, and Playwright E2E tests.

## Structure

```
tests/
├── unit/                    # No Ollama required, all I/O mocked
│   ├── backend/
│   │   ├── agents/          # AutoAgent v2, DefaultAgent, domain orchestrator
│   │   │   └── auto_agent_phases/  # PhaseContext, Blueprint, Scaffold, etc.
│   │   ├── api/             # FastAPI router tests (TestClient)
│   │   └── utils/           # Core utilities, LLM, memory, tools
│   ├── llm/                 # Token propagation, OllamaClient
│   ├── test_import_cost.py  # phase_context loads <100 modules (was 1567)
│   └── fixtures/            # fastapi_app, client, tmp fixtures
├── integration/             # Real file I/O, no Ollama
└── e2e/                     # Playwright, Ollama-free (mocked responses)
```

## Running

```bash
# All unit tests
pytest tests/unit/ -q

# Single file
pytest tests/unit/backend/agents/auto_agent_phases/test_blueprint_phase.py -v

# By name
pytest -k "test_blueprint"

# With coverage
pytest tests/unit/ --cov=backend --cov-report=term-missing

# Integration
pytest tests/integration/ -q

# E2E (requires running server + playwright)
playwright install chromium
pytest tests/e2e/ -m e2e
```

## Conventions

- All unit tests marked `@pytest.mark.unit`
- All integration tests marked `@pytest.mark.integration`
- Mock all LLM calls: `MagicMock()` for `llm_manager` — no Ollama needed
- Use `tmp_path` pytest fixture for all file I/O
- Patch lazily-imported classes at their source module path (not import site)
- Container overrides: `main_container.core.logging.logger.override(mock)`

## Import Cost Test

`tests/unit/test_import_cost.py` enforces:
- `import backend.agents.auto_agent_phases.phase_context` loads <100 modules
- No chromadb pulled in at startup
