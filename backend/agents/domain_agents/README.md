# backend/agents/domain_agents/

Swarm de agentes especializados por dominio. Coordina múltiples agentes que trabajan en paralelo sobre un proyecto, cada uno con su área de responsabilidad.

## Agentes

| Archivo | Agente | Responsabilidad |
|---------|--------|----------------|
| `architect_agent.py` | `ArchitectAgent` | Diseño de arquitectura, decisiones de alto nivel, debate con Auditor |
| `developer_agent.py` | `DeveloperAgent` | Generación de código; se instancia como pool de 3 workers |
| `auditor_agent.py` | `AuditorAgent` | Revisión de código, cumplimiento, seguridad; debate con Architect |
| `devops_agent.py` | `DevOpsAgent` | Infraestructura, CI/CD, configuración de despliegue |

## Orquestación

El `DomainAgentOrchestrator` (`../domain_agent_orchestrator.py`) coordina el swarm:

1. Recibe una tarea de alto nivel
2. Despacha sub-tareas a los agentes según dominio
3. Los agentes comparten estado via `Blackboard` (`../orchestrators/blackboard.py`)
4. `SelfHealingLoop` reintenta tareas fallidas con contexto de error
5. `DebateNodeRunner` enfrenta a `ArchitectAgent` vs `AuditorAgent` para decisiones controvertidas
6. `CheckpointManager` guarda snapshots del estado del swarm

## Blackboard

Estado compartido entre agentes:

```python
blackboard.write(key, value, agent_id)   # Escribe resultado
blackboard.read(key)                      # Lee resultado
blackboard.subscribe(key, callback)       # Reacciona a cambios
blackboard.get_history(key)               # Historial de cambios
```
