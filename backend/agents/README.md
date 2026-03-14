# backend/agents/

Capa de agentes IA. Dos modos principales: **chat interactivo** (`DefaultAgent`) y **generación de proyectos por fases** (`AutoAgent`).

## Archivos principales

| Archivo | Responsabilidad |
|---------|----------------|
| `core_agent.py` | Clase base `CoreAgent`: gestión de kernel, herramientas, historial |
| `default_agent.py` | Agente de chat; compone 3 mixins sobre `CoreAgent` |
| `auto_agent.py` | Pipeline secuencial de 25+ fases para generar proyectos completos |
| `domain_agent_orchestrator.py` | Orquesta el swarm de agentes por dominio |
| `simple_chat_agent.py` | Variante ligera sin herramientas (chat directo) |
| `auto_benchmarker.py` | Benchmarking end-to-end de generación de proyectos |
| `phase_benchmarker.py` | Benchmarking por fase individual |
| `monitor_agents.py` | Agentes de monitorización del sistema |

## DefaultAgent

Compone tres mixins sobre `CoreAgent`:

```
CoreAgent
  └── IntentRoutingMixin    → detecta keywords de intención, elige modelo/rol
  └── ToolLoopMixin         → ejecuta bucle tool-call → observe → responde
  └── ContextSummarizerMixin → resume contexto cuando se acerca al límite de tokens
```

Flujo de una petición:
1. `chat(user_input)` → `_process_user_input()` → `IntentRoutingMixin` selecciona rol
2. LLM genera respuesta con posibles tool-calls
3. `ToolLoopMixin` ejecuta herramientas, obtiene observaciones, vuelve al LLM
4. Si el contexto supera `max_context_tokens`, `ContextSummarizerMixin` comprime
5. Respuesta final formateada con `_format_response()`

## AutoAgent — Tiers de modelo

| Tier | Parámetros | Fases activas |
|------|-----------|---------------|
| Full | ≥30B | Todas |
| Slim | 9–29B | Sin `DynamicDocumentation`, `CICDHealing`, `PlanValidation` |
| Nano | ≤8B | Slim + sin `ExhaustiveReviewRepair`, `LicenseCompliance`, `ApiContract`, `TestPlanning`, `ComponentTree`, `Clarification`; activa `opt6_active_shadow` |

## Subdirectorios

| Directorio | Contenido |
|-----------|-----------|
| `auto_agent_phases/` | 39 implementaciones de fases + `PhaseContext`, `base_phase`, helpers |
| `domain_agents/` | Architect, Developer (pool ×3), Auditor, DevOps |
| `mixins/` | `ContextSummarizerMixin`, `IntentRoutingMixin`, `ToolLoopMixin` |
| `orchestrators/` | Blackboard, TaskDAG, SelfHealingLoop, DebateNodeRunner, CheckpointManager |
