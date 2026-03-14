# backend/utils/core/llm/

Capa de abstracción sobre Ollama: cliente HTTP, carga de prompts, tracking de tokens, generación en paralelo.

## Archivos

| Archivo | Clase | Responsabilidad |
|---------|-------|----------------|
| `ollama_client.py` | `OllamaClient` | Cliente HTTP para Ollama; `chat()` sync + `achat()` async, function calling |
| `prompt_loader.py` | `PromptLoader` | Singleton; carga prompts YAML desde `prompts/`; DB-first via `PromptRepository` |
| `prompt_repository.py` | `PromptRepository` | CRUD de prompts en SQLite; parámetros nombrados (`:role`, `:name`) |
| `llm_response_parser.py` | `LLMResponseParser` | Extrae bloques de código, JSON, estructuras del texto LLM |
| `token_tracker.py` | `TokenTracker` | Cuenta tokens usados por sesión y por modelo |
| `parallel_generator.py` | `ParallelGenerator` | Genera múltiples archivos en paralelo con rate limiting |
| `context_saturation.py` | `ContextSaturation` | Detecta y gestiona saturación de contexto |
| `model_router.py` | `ModelRouter` | Enruta peticiones al modelo más apropiado según carga y capacidad |
| `model_health_monitor.py` | `ModelHealthMonitor` | Monitoriza latencia y disponibilidad de modelos Ollama |
| `llm_recorder.py` | `LLMRecorder` | Graba/reproduce llamadas LLM para tests y debugging |
| `benchmark_model_selector.py` | `BenchmarkModelSelector` | Selecciona modelos óptimos basándose en resultados de benchmark |
| `benchmark_rubrics.py` | Constantes | Rúbricas de evaluación para benchmarks |
| `models.py` | Dataclasses | `LLMRequest`, `LLMResponse`, `TokenUsage` |

## OllamaClient

```python
client = OllamaClient(model="qwen2.5:4b", base_url="http://localhost:11434")

# Chat sincrónico
response = client.chat(messages=[{"role": "user", "content": "Hola"}])

# Chat asíncrono
response = await client.achat(messages=..., tools=[...])

# Function calling
response = client.chat(
    messages=messages,
    tools=[{"type": "function", "function": {"name": "write_file", ...}}]
)
```

## PromptLoader

```python
loader = PromptLoader.get_instance()

# Carga un par system/user de un YAML
system, user = loader.get_prompt("code_gen_v2", variables={
    "file_path": "src/main.py",
    "purpose": "Entry point"
})
```

Los prompts se buscan en este orden:
1. Base de datos SQLite (`PromptRepository`) — permite edición en runtime
2. Archivo YAML en `prompts/` — fallback de filesystem

## LLMResponseParser

```python
parser = LLMResponseParser()

# Extrae bloque de código para un archivo específico (language-aware)
code = parser.extract_code_block_for_file(llm_text, "src/app.ts")

# Extrae JSON del texto
data = parser.extract_json(llm_text)

# Extrae lista de rutas de archivos
files = parser.extract_file_list(llm_text)
```
