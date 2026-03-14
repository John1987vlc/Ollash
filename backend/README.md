# backend/

Núcleo del servidor Ollash. Expone la API FastAPI y contiene todos los agentes, servicios, utilidades y configuración.

## Estructura

```
backend/
├── agents/          Agentes IA: DefaultAgent, AutoAgent, swarm de dominio
├── api/             FastAPI app factory, routers, dependencias
├── core/            Contenedores DI, configuración, kernel
├── interfaces/      Interfaces/ABCs para romper dependencias circulares
├── services/        Servicios de sesión, LLM client manager, event bridge
├── utils/
│   ├── core/        Utilidades transversales (IO, LLM, memoria, sistema, herramientas)
│   └── domains/     Herramientas por dominio (auto_generation, git, network, etc.)
└── config/          JSONs de configuración (modelos LLM, herramientas, features)
```

## Entry points

| Archivo | Descripción |
|---------|-------------|
| `run_web.py` (raíz) | Levanta uvicorn con `backend.api.app.create_app()` en puerto 5000 |
| `ollash_cli.py` (raíz) | CLI: `agent`, `swarm`, `benchmark`, `chat`, `security-scan` |

## Convenciones

- **Type hints** obligatorios en todas las funciones.
- **Logs** con `AgentLogger`, nunca `print()`.
- **Sin imports circulares** — usar `backend/interfaces/` como capa de indirección.
- Operaciones destructivas pasan por `ConfirmationManager`.
- Todos los comandos shell pasan por `PolicyEnforcer`.
