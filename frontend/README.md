# frontend/

SPA (Single Page Application) servida por FastAPI. Usa Jinja2 para templates y Vite para bundling opcional de TypeScript.

## Estructura

```
frontend/
├── core/
│   ├── config_manager.py    Gestión de configuración del cliente
│   └── service_manager.py   Servicios del cliente (API calls, estado)
├── middleware.py             Middleware FastAPI (CORS, auth, logging)
├── schemas/                 Modelos Pydantic de request/response
├── services/                Servicios Python del frontend (vacío — en desarrollo)
├── static/                  Assets estáticos
│   ├── css/                 Estilos por página
│   ├── js/                  JavaScript legacy + TypeScript
│   │   ├── core/            Módulos TS: store, SSE, theme, chat
│   │   ├── pages/           JS por página (chat.js, projects.js, etc.)
│   │   ├── index.ts         Entry point Vite
│   │   └── types/           Declaraciones de tipos CDN (cdn.d.ts)
│   └── dist/                Bundle Vite (generado, no en git)
└── templates/               Templates Jinja2
    ├── base.html            Layout base con CDN scripts
    ├── index.html           SPA principal — incluye todos los pages/
    └── pages/               30+ partials de página
```

## Schemas Pydantic

| Archivo | Modelos |
|---------|---------|
| `chat_schemas.py` | `ChatRequest`, `ChatResponse`, `Message` |
| `cybersecurity_schemas.py` | `ScanRequest`, `VulnerabilityReport` |
| `git_schemas.py` | `CommitRequest`, `GitStatus`, `DiffResponse` |
| `knowledge_schemas.py` | `KnowledgeQuery`, `KnowledgeEntry` |
| `operations_schemas.py` | `TaskRequest`, `OperationResult` |

## Templates

`index.html` extiende `base.html` e incluye todos los partials de `pages/`:

```html
{% extends "base.html" %}
{% block content %}
    {% include 'pages/chat.html' %}
    {% include 'pages/create_project.html' %}
    {% include 'pages/swarm.html' %}
    ...  (30+ páginas)
{% endblock %}
```

La navegación entre páginas es JS puro (SPA): muestra/oculta divs sin recargar.

## TypeScript (Vite)

Módulos TS en `static/js/core/`:

| Módulo | Responsabilidad |
|--------|----------------|
| `store.ts` | Estado global reactivo de la SPA |
| `module-registry.ts` | Registro de módulos de página con lazy loading |
| `sse-connection-manager.ts` | Gestión de conexiones SSE (reconexión automática) |
| `theme-manager.ts` | Cambio de tema claro/oscuro |
| `chat-module.ts` | Módulo de chat con streaming |

### Build Vite

```bash
npm run build    # genera frontend/static/dist/
# Luego:
USE_VITE_ASSETS=true python run_web.py
```

Sin `USE_VITE_ASSETS`, la app sirve los JS legacy individuales (20+ script tags en `base.html`).

## CDN libs (no bundleadas)

Declaradas en `static/js/types/cdn.d.ts` para tipado TypeScript:
Cytoscape, vis-network, Mermaid, Monaco Editor, Chart.js, Xterm, Marked, Highlight.js
