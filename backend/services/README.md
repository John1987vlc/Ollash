# backend/services/

Servicios de alto nivel que conectan la capa de API con los agentes y el LLM.

## Archivos

| Archivo | Clase | Responsabilidad |
|---------|-------|----------------|
| `language_manager.py` | `LanguageManager` | Gestiona el ciclo de vida de los modelos Ollama cargados |
| `llm_client_manager.py` | `LLMClientManager` | Factory de `OllamaClient` por rol; mapea `"coder"` → modelo concreto |
| `chat_session_manager.py` | `ChatSessionManager` | Crea, almacena y recupera sesiones de chat; soporta `mode="coding"` con `DefaultAgent` |
| `chat_event_bridge.py` | `ChatEventBridge` | Puente entre `DefaultAgent` (sync) y el SSE endpoint (async); suscribe 30+ tipos de evento |
| `project_index.py` | `ProjectIndex` | Índice RAG por sesión: indexa el proyecto en background, expone `search(query)` |

## Modos de sesión

`ChatSessionManager.create_session()` acepta un parámetro `mode`:

| `mode` | Agente usado | Herramientas | Casos de uso |
|--------|-------------|--------------|--------------|
| `"simple"` (default) | `SimpleChatAgent` | Ninguna | Q&A ligero, preguntas generales |
| `"coding"` | `DefaultAgent` | 52 tools completas | Editar código, correr tests, refactoring |

```python
# Modo simple (por defecto)
POST /api/chat  {"message": "...", "mode": "simple"}

# Modo coding — con herramientas + contexto de proyecto
POST /api/chat  {
  "message": "Arregla el bug en src/parser.py",
  "mode": "coding",
  "project_path": "/ruta/mi-proyecto"
}
```

## ChatSessionManager

```python
# Crear sesión de codificación con proyecto
session_id = mgr.create_session(
    mode="coding",
    project_path="/ruta/mi-proyecto",
)

# Enviar mensaje (ejecuta en hilo background)
mgr.send_message(session_id, "Refactoriza la clase AuthManager")

# Historial
history = mgr.get_session_history(session_id)
```

Al crear una sesión `"coding"`, el manager:
1. Carga el system prompt de `prompts/roles/interactive_coding_agent.yaml`
2. Inyecta el árbol de archivos del proyecto en el prompt
3. Appends `CLAUDE.md` / `OLLASH.md` del proyecto si existe
4. Crea un `ProjectIndex` y lanza la indexación RAG en background
5. Inyecta el `ProjectIndex` en `FileSystemTools` del agente (para `search_codebase`)

## ChatEventBridge

Convierte eventos síncronos del agente en el SSE stream:

```python
bridge = ChatEventBridge(event_publisher)

# El agente publica vía EventPublisher → ChatEventBridge lo encola
event_publisher.publish("stream_chunk", {"text": "pytest line...", "stream": "stdout"})

# El endpoint SSE lee con iter_events()
for sse_chunk in bridge.iter_events():
    yield sse_chunk  # "data: {...}\n\n"
```

Eventos clave suscritos: `tool_call`, `tool_output`, `stream_chunk` (streaming shell),
`final_answer`, `error`, `thinking`, `file_generated`, y 25+ más.

## ProjectIndex

Índice RAG por sesión para búsqueda semántica de código:

```python
idx = ProjectIndex("/ruta/mi-proyecto")
idx.start_background_index()   # lanza indexación en daemon thread

# En un tool call posterior:
result = idx.search("authentication middleware")
# → "**src/auth.py** (lines 1–45)\n```\nclass AuthMiddleware...\n```"
```

Si el índice no está listo, `search()` hace un fallback a grep por nombre de archivo.
La tool `search_codebase` en `FileSystemTools` delega a esta clase.
