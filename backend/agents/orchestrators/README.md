# backend/agents/orchestrators/

Infraestructura de orquestación para el swarm de agentes de dominio.

## Archivos

| Archivo | Clase principal | Responsabilidad |
|---------|----------------|----------------|
| `blackboard.py` | `Blackboard` | Estado compartido con pub/sub entre agentes del swarm |
| `task_dag.py` | `TaskDAG` | Grafo dirigido de tareas con dependencias; ejecuta en orden topológico |
| `self_healing_loop.py` | `SelfHealingLoop` | Reintenta fases fallidas con `RescuePhase` como contexto de recuperación |
| `debate_node_runner.py` | `DebateNodeRunner` | Enfrenta a dos agentes (Architect vs Auditor) en debate estructurado |
| `checkpoint_manager.py` | `CheckpointManager` | Guarda/restaura snapshots del estado del swarm (async, con `asyncio.to_thread`) |
| `phase_failure_handler.py` | `PhaseFailureHandler` | Maneja errores de fases, decide si reintentar o escalar |

## Flujo de ejecución del swarm

```
DomainAgentOrchestrator
  ├── construye TaskDAG con dependencias entre sub-tareas
  ├── ejecuta tareas en orden topológico
  │     ├── cada tarea → agente de dominio correspondiente
  │     └── resultado → Blackboard
  ├── SelfHealingLoop intercepta fallos:
  │     ├── crea RescuePhase con contexto del error
  │     └── reintenta con estrategia adaptada
  └── CheckpointManager guarda estado tras cada fase exitosa
```

## TaskDAG

Permite definir dependencias entre tareas del swarm:

```python
dag = TaskDAG()
dag.add_task("architecture", agent=architect, depends_on=[])
dag.add_task("implementation", agent=developer, depends_on=["architecture"])
dag.add_task("review", agent=auditor, depends_on=["implementation"])
await dag.execute(blackboard)
```

## RescuePhase

Generada dinámicamente por `AutoAgent._request_rescue_plan()` cuando una fase falla. No escribe archivos — solo registra contexto de recuperación para que las fases siguientes puedan adaptarse.
