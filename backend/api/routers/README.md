# backend/api/routers/

46 APIRouter FastAPI. Migrados desde Flask blueprints. **5 implementados** + **40 stubs** con endpoints `TODO`.

## Routers implementados

| Router | Prefijo | Descripción |
|--------|---------|-------------|
| `health_router.py` | `/api/health` | Health checks y estado del sistema |
| `chat_router.py` | `/api/chat` | Chat con DefaultAgent; SSE para streaming |
| `auto_agent_router.py` | `/api/auto-agent` | Generación de proyectos con AutoAgent |
| `terminal_router.py` | `/api/terminal` | WebSocket para terminal interactiva |
| `checkpoints_router.py` | `/api/checkpoints` | Gestión de snapshots de proyectos |
| `git_router.py` | `/api/git` | `GET /status`, `GET /diff`, `POST /commit`, `GET /log` |
| `fragments_router.py` | `/api/fragments` | `GET /api/fragments`, `POST /api/fragments/favorite` |
| `insights_router.py` | `/api/reports` | `GET /weekly` — reporte semanal de actividad |

## Stubs (pendientes de implementar)

Todos tienen la estructura básica del router y devuelven `{"status": "not_implemented"}`. Áreas pendientes:

- Alertas, análisis, analytics, artefactos, auditoría
- Automatizaciones, benchmarks, CI/CD, costes
- Cyberseguridad, decisiones, exportaciones
- Grafos de conocimiento, conocimiento, aprendizaje
- Métricas, monitores, multimodal
- Operaciones, pair programming, plugins, políticas
- Grafos de proyecto, prompt studio, refactoring, refinement
- Resiliencia, sandbox, swarm, traductor
- Triggers, tuning, webhooks

## Convención de implementación

```python
# Nombre: {feature}_router.py
# Prefijo: /api/{feature}
from fastapi import APIRouter, Depends
from backend.api.deps import get_service

router = APIRouter(prefix="/api/feature", tags=["feature"])

@router.get("/")
async def list_items(svc = Depends(get_service)):
    ...
```

## Páginas HTML (pages_router.py)

Sirve las páginas Jinja2 del SPA. Cada ruta devuelve `TemplateResponse` con el contexto necesario.
