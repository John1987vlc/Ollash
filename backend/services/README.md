# backend/services/

Servicios de alto nivel que conectan la capa de API con los agentes y el LLM.

## Archivos

| Archivo | Clase | Responsabilidad |
|---------|-------|----------------|
| `language_manager.py` | `LanguageManager` | Gestiona el ciclo de vida de los modelos Ollama cargados |
| `llm_client_manager.py` | `LLMClientManager` | Factory de `OllamaClient` por rol; mapea `"coder"` → modelo concreto |
| `chat_session_manager.py` | `ChatSessionManager` | Crea, almacena y recupera sesiones de chat con historial |
| `chat_event_bridge.py` | `ChatEventBridge` | Puente entre `DefaultAgent` (sync) y el SSE endpoint (async) |

## LLMClientManager

Punto central de acceso a los modelos LLM:

```python
manager = LLMClientManager()
client = manager.get_client("coder")    # → OllamaClient apuntando al modelo coder
client = manager.get_client("security") # → OllamaClient apuntando al modelo security

# Mapping en backend/config/llm_models.json:
# "agent_roles": { "coder": "qwen2.5-coder:7b", "security": "... }
```

## ChatSessionManager

```python
session_id = await manager.create_session(project_name="my_app")
await manager.append_message(session_id, role="user", content="...")
history = await manager.get_history(session_id)
await manager.clear_session(session_id)
```

## ChatEventBridge

Convierte llamadas síncronas del agente en eventos SSE para el browser:

```python
bridge = ChatEventBridge(queue)
bridge.emit("token", {"text": "Hola"})   # → encolado en asyncio.Queue
bridge.emit("done", {})
```
