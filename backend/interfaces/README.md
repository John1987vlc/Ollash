# backend/interfaces/

Interfaces abstractas (ABCs) para romper dependencias circulares entre módulos. Cualquier módulo puede importar desde aquí sin crear ciclos de importación.

## Interfaces

| Archivo | Interfaz | Implementada por |
|---------|----------|-----------------|
| `iagent_phase.py` | `IAgentPhase` | `BasePhase` en `auto_agent_phases/base_phase.py` |
| `imemory_system.py` | `IMemorySystem` | `EpisodicMemory`, `ErrorKnowledgeBase` |
| `imodel_provider.py` | `IModelProvider` | `OllamaClient`, `LLMClientManager` |
| `itool_executor.py` | `IToolExecutor` | `AsyncToolExecutor`, `ToolRegistry` |

## Cuándo añadir una interfaz aquí

Si `module_A` necesita importar un tipo de `module_B` y `module_B` también importa de `module_A` (ciclo), mover el tipo a `interfaces/` y hacer que ambos importen desde aquí.

## Patrón de uso

```python
# En lugar de importar la clase concreta (crea ciclo):
# from backend.utils.core.memory.episodic_memory import EpisodicMemory

# Importar la interfaz:
from backend.interfaces.imemory_system import IMemorySystem

def process(memory: IMemorySystem) -> None:
    memory.record_episode(...)
```
