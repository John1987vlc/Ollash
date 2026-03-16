# backend/agents

Agent implementations for Ollash.

## Agents

| File | Class | Description |
|------|-------|-------------|
| `auto_agent.py` | `AutoAgent` | 10-phase project generator (4B-optimized) |
| `default_agent.py` | `DefaultAgent` | Chat agent with tool loop (IntentRouting + ContextSummarizer) |
| `core_agent.py` | `CoreAgent` | Base class: file ops, model selection, context management |

## Sub-packages

| Directory | Contents |
|-----------|---------|
| `auto_agent_phases/` | 10 pipeline phases + PhaseContext + BasePhase |
| `domain_agents/` | Swarm: ArchitectAgent, DeveloperAgent ×3, AuditorAgent, DevOpsAgent |
| `mixins/` | ContextSummarizerMixin, IntentRoutingMixin, ToolLoopMixin |
| `orchestrators/` | Blackboard, TaskDAG, SelfHealingLoop, DebateNodeRunner, CheckpointManager |

## AutoAgent Quick Usage

```python
from backend.agents.auto_agent import AutoAgent

agent = AutoAgent(
    llm_manager=...,
    file_manager=...,
    event_publisher=...,
    logger=...,
    generated_projects_dir=Path("generated_projects"),
)

# Full run (10 phases)
project_path = agent.run("A FastAPI REST API with SQLite", "my_api")

# Structure preview only (phases 1+2, no files written)
structure = agent.generate_structure_only("A FastAPI REST API", "my_api")
# → {"files": [...], "project_type": "api", "tech_stack": ["python", "fastapi"]}
```

## DefaultAgent Tool Loop

`DefaultAgent` composes three mixins on `CoreAgent`:
1. `IntentRoutingMixin` — routes to the correct model role (coder/planner/…)
2. `ToolLoopMixin` — iterates tool-call → execute → observe until done
3. `ContextSummarizerMixin` — auto-summarizes when approaching token limit

## Domain Agent Swarm

`DomainAgentOrchestrator` dispatches tasks to specialized agents via a shared `Blackboard`. Supports `DebateNodeRunner` (Architect vs Auditor) and `SelfHealingLoop`.
