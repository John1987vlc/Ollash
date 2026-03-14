# tests/

Suite de tests de Ollash. Tres niveles: **unit**, **integration**, **e2e**.

## Estructura

```
tests/
├── conftest.py          Registro central de fixtures (pytest_plugins)
├── fixtures/            Módulos de fixtures compartidas
│   ├── agent_fixtures.py    project_root, mock_kernel, default_agent
│   ├── llm_fixtures.py      block_ollama_globally (autouse), mock_ollama
│   ├── fastapi_fixtures.py  fastapi_app, client (TestClient)
│   └── e2e_fixtures.py      server_port, base_url, uvicorn server, Playwright page
├── unit/                Tests unitarios (mock de todo I/O)
│   ├── backend/agents/  ~60 tests de fases AutoAgent y DefaultAgent
│   ├── backend/utils/   ~80 tests de utilidades core y dominios
│   ├── frontend/        3 tests de schemas y middleware
│   └── *.py             Tests de import cost, enterprise features, etc.
├── integration/         Tests de integración (sin mock de LLM)
│   ├── agents_swarm/    Tests del swarm de dominio
│   ├── llm_integration/ Tests de OllamaClient (necesita Ollama corriendo)
│   ├── system_flows/    Flujos end-to-end de sistema
│   └── test_cli_entry.py Validación estructural del CLI
├── e2e/                 Tests E2E con Playwright (necesita servidor + chromium)
└── manual/              Tests manuales (no corren en CI)
```

## Correr tests

```bash
# Unit (default, siempre corren en CI)
pytest tests/unit/

# Integration
pytest tests/integration/

# E2E (necesita servidor corriendo + playwright install chromium)
pytest tests/e2e/ -m e2e

# Un archivo específico
pytest tests/unit/backend/agents/auto_agent_phases/test_file_content_generation_phase.py

# Por nombre
pytest -k "test_my_function"

# Con cobertura
pytest tests/unit/ --cov=backend --cov-report=html
```

## Configuración (pytest.ini)

```ini
[pytest]
asyncio_mode = auto          # async fixtures/tests sin @pytest.mark.asyncio
filterwarnings = error        # DeprecationWarnings son errores
markers:
  unit: Tests unitarios
  integration: Tests de integración
  e2e: Tests E2E (requieren servidor)
```

## Fixtures clave

### `block_ollama_globally` (autouse, session)

Bloquea todas las llamadas reales a Ollama en unit tests. Si un test necesita llamar a Ollama, usar `@pytest.mark.integration`.

### `mock_ollama`

Mock de `OllamaClient` que devuelve respuestas predefinidas. Usar en tests de agentes.

### `client` (TestClient FastAPI)

```python
def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
```

### `default_agent`

Instancia de `DefaultAgent` con kernel mockeado, lista para tests.

## Convenciones

- Tests unitarios: marcar con `@pytest.mark.unit`
- Mockear todo I/O externo (Ollama, filesystem, git)
- Mirror de estructura: `tests/unit/backend/agents/` espeja `backend/agents/`
- Cuando se parchea una clase importada lazily dentro de una función, parchear en el path del módulo fuente (no en el módulo importador)
- `FragmentCache` tests: siempre `async def` + `await cache._init_db()` en fixture
- `FileContentGenerator` legacy emite `DeprecationWarning` → añadir `pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")`

## CI

GitHub Actions `.github/workflows/ci.yml` corre `pytest tests/unit tests/integration` en cada push a `master`. Los E2E se saltan en CI (requieren servidor Ollama + Playwright).
