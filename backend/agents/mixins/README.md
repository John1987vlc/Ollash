# backend/agents/mixins/

Mixins que extienden `CoreAgent` con comportamientos reutilizables. `DefaultAgent` hereda los tres.

## Mixins

### `ContextSummarizerMixin` (`context_summarizer_mixin.py`)

Comprime el historial de conversación cuando se acerca al límite de tokens.

- Observa `ctx.token_count` vs `max_context_tokens` (configurado en `tool_settings.json`)
- Al superar el umbral: llama al LLM para generar un resumen comprimido del historial
- Sustituye mensajes antiguos por el resumen, preservando los N últimos mensajes

### `IntentRoutingMixin` (`intent_routing_mixin.py`)

Detecta la intención del usuario y selecciona el modelo/rol LLM apropiado.

- Analiza keywords en el mensaje (ej. "código", "seguridad", "arquitectura")
- Mapea intención → rol de agente (ej. `"coder"`, `"security"`, `"architect"`)
- El rol determina qué modelo Ollama se usa (ver `backend/config/llm_models.json`)

### `ToolLoopMixin` (`tool_loop_mixin.py`)

Implementa el bucle de ejecución de herramientas:

```
LLM genera respuesta
  └─ si hay tool_calls:
       ├── ejecuta cada herramienta via ToolRegistry
       ├── añade observaciones al historial
       └── vuelve al LLM con los resultados (hasta max_iterations)
  └─ si no hay tool_calls: respuesta final
```

- Máximo de iteraciones configurable para evitar bucles infinitos
- Pasa tool_calls por `ConfirmationManager` antes de ejecutar operaciones destructivas
