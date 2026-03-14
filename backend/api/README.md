# backend/api/

Capa de API FastAPI. Factory pattern: `create_app()` en `app.py` crea y configura la aplicación.

## Archivos principales

| Archivo | Responsabilidad |
|---------|----------------|
| `app.py` | Factory `create_app()`: registra routers, monta estáticos, configura lifespan DI, Jinja2Templates |
| `deps.py` | Providers de dependencias FastAPI (reemplazan `app.config.get()`); decorador `service_error_handler` |
| `vite.py` | `asset_url(name)`: lee `frontend/static/dist/.vite/manifest.json` para URLs de assets Vite |

## Subdirectorios

| Directorio | Contenido |
|-----------|-----------|
| `routers/` | 46 APIRouter files — 5 implementados + 40 stubs con TODO |

## Configuración de la app

```python
# run_web.py
app = create_app()
uvicorn.run(app, host="0.0.0.0", port=5000)

# Variables de entorno relevantes
OLLAMA_URL=http://localhost:11434   # URL del servidor Ollama
USE_VITE_ASSETS=true                # Servir bundle Vite en lugar de JS legacy
```

## Patrón de dependencias (deps.py)

```python
# En lugar de flask.current_app.config.get("service")
from backend.api.deps import get_llm_manager

@router.get("/chat")
async def chat(llm: LLMClientManager = Depends(get_llm_manager)):
    ...
```

## Assets frontend

- **Modo desarrollo** (`USE_VITE_ASSETS=false`): sirve archivos JS/CSS individuales desde `frontend/static/`
- **Modo producción** (`USE_VITE_ASSETS=true`): sirve bundle generado por Vite desde `frontend/static/dist/`; requiere `npm run build` previo

## SSE (Server-Sent Events)

Flujo de eventos en tiempo real:
```
EventPublisher (sync) → asyncio.Queue → loop.call_soon_threadsafe() → StreamingResponse async generator → browser
```
