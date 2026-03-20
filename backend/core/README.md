# backend/core/

Configuración central e inyección de dependencias. Todo el sistema de DI usa `dependency-injector`.

## Archivos

| Archivo | Responsabilidad |
|---------|----------------|
| `containers.py` | `ApplicationContainer` + jerarquía completa de contenedores |
| `config.py` | Modelos Pydantic de configuración de la aplicación |
| `config_loader.py` | Carga configs desde JSON, `.env` y variables de entorno |
| `config_schemas.py` | Schemas Pydantic v2 para validar configs |
| `kernel.py` | `AgentKernel`: núcleo de ejecución de agentes (herramientas, estado, logging) |
| `language_standards.py` | Estándares de cumplimiento por lenguaje de programación |

## Jerarquía de contenedores

```
ApplicationContainer
└── CoreContainer
    ├── LoggingContainer
    │     ├── core.logging.logger          → AgentLogger
    │     ├── core.logging.agent_kernel    → AgentKernel
    │     └── core.logging.event_publisher → EventPublisher
    ├── StorageContainer
    │     ├── core.storage.file_manager    → FileManager
    │     ├── core.storage.response_parser → LLMResponseParser
    │     ├── core.storage.fragment_cache  → FragmentCache
    │     └── core.storage.file_validator  → FileValidator
    ├── AnalysisContainer
    │     ├── core.analysis.code_quarantine        → CodeQuarantine
    │     ├── core.analysis.dependency_graph       → DependencyGraph
    │     ├── core.analysis.rag_context_selector   → RAGContextSelector
    │     ├── core.analysis.vulnerability_scanner  → VulnerabilityScanner
    │     └── core.analysis.shadow_evaluator       → ShadowEvaluator
    ├── SecurityContainer
    │     ├── core.security.permission_manager → PermissionManager
    │     └── core.security.policy_enforcer    → PolicyEnforcer
    └── MemoryContainer
          ├── core.memory.error_knowledge_base → ErrorKnowledgeBase
          └── core.memory.episodic_memory      → EpisodicMemory
```

## Uso

```python
from backend.core.containers import ApplicationContainer

main_container = ApplicationContainer()
main_container.wire(modules=[...])

# Acceso en tests
main_container.core.logging.logger.override(mock_logger)

# Acceso en código
logger = main_container.core.logging.logger()
```

## IMPORTANTE: rutas de acceso

Usar **siempre** la ruta completa con sub-contenedor:
- ✅ `core.logging.logger`
- ❌ `core.logger` (ruta antigua — eliminada en Sprint 2)

## config_schemas.py — SeniorReview validators (Sprint 20)

`SeniorReviewIssue` and `SeniorReviewOutput` in `config_schemas.py` have `@field_validator(mode="before")` validators that normalise LLM vocabulary before Pydantic's `Literal` check:

| Input | Normalised |
|-------|-----------|
| `"warning"`, `"warn"` | `"medium"` |
| `"error"`, `"err"`, `"major"`, `"important"` | `"high"` |
| `"blocker"`, `"fatal"`, `"severe"` | `"critical"` |
| `"info"`, `"information"`, `"minor"` | `"low"` |
| unknown strings | `"medium"` |
| `"pass"`, `"ok"`, `"success"`, `"clean"`, `"good"` (status) | `"passed"` |
| unknown status strings | `"failed"` |
