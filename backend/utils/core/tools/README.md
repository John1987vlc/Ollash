# backend/utils/core/tools/

Sistema de herramientas: registro, decorador, ejecución async y sandboxes.

## Archivos

| Archivo | Clase | Responsabilidad |
|---------|-------|----------------|
| `tool_registry.py` | `ToolRegistry` | Auto-descubre y registra herramientas; auto-walk de `backend/utils/domains/` |
| `tool_decorator.py` | `@ollash_tool` | Decorador para registrar implementaciones de herramientas |
| `tool_interface.py` | `ITool` | Interfaz base de herramientas |
| `async_tool_executor.py` | `AsyncToolExecutor` | Ejecuta herramientas de forma asíncrona con timeout |
| `all_tool_definitions.py` | Constantes | Lista consolidada de definiciones de todas las herramientas |
| `tool_span_manager.py` | `ToolSpanManager` | Tracking de spans de ejecución para observabilidad |
| `git_pr_tool.py` | Funciones | Herramientas especializadas de Pull Request |
| `network_sandbox.py` | `NetworkSandbox` | Sandbox de red: bloquea conexiones no autorizadas |
| `scripting_sandbox.py` | `ScriptingSandbox` | Sandbox para ejecución de scripts |
| `wasm_sandbox.py` | `WasmSandbox` | Sandbox WebAssembly para código no confiable |

## Registrar una herramienta nueva

```python
from backend.utils.core.tools.tool_decorator import ollash_tool

@ollash_tool(
    name="my_tool",
    description="Descripción clara para el LLM",
    parameters={
        "file_path": {"type": "string", "description": "Ruta del archivo"},
        "content": {"type": "string", "description": "Contenido a escribir"}
    },
    toolset_id="file_system_tools",
    agent_types=["code", "system"],
    is_async_safe=True,
)
async def my_tool_impl(self, file_path: str, content: str) -> str:
    ...
    return "OK"
```

El archivo debe estar en `backend/utils/domains/{domain}/` — el `ToolRegistry` lo descubre automáticamente en el startup.

## ToolRegistry

```python
registry = ToolRegistry.get_instance()

# Obtener definiciones para pasar al LLM
tools = registry.get_tool_definitions(agent_types=["code"])

# Ejecutar una herramienta
result = await registry.execute_tool(
    tool_name="write_file",
    params={"file_path": "src/main.py", "content": "..."},
    agent_context=ctx
)

# Filtrar por toolset
fs_tools = registry.get_by_toolset("file_system_tools")
```

## Sandboxes

| Sandbox | Uso |
|---------|-----|
| `NetworkSandbox` | Bloquea salidas de red a hosts no permitidos |
| `ScriptingSandbox` | Aísla ejecución de Python/Bash arbitrario |
| `WasmSandbox` | Ejecuta código WASM en entorno completamente aislado |

Los sandboxes se activan según el nivel configurado en `tool_settings.json`.
