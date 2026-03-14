# backend/utils/core/system/

Infraestructura de sistema: logging, alertas, automatizaciones, CI/CD, triggers, tareas y base de datos.

## Archivos

| Archivo | Clase | Responsabilidad |
|---------|-------|----------------|
| `agent_logger.py` | `AgentLogger` | Logger estructurado para agentes; reemplaza `print()` |
| `structured_logger.py` | `StructuredLogger` | Logger JSON para observabilidad y exportación a métricas |
| `event_publisher.py` | `EventPublisher` | Publica eventos sync → consumidos por SSE en FastAPI |
| `alert_manager.py` | `AlertManager` | Gestión de alertas y notificaciones del sistema |
| `notification_manager.py` | `NotificationManager` | Envía notificaciones (email, webhook, Slack) |
| `trigger_manager.py` | `TriggerManager` | Triggers unificados: cron, git, webhook, file watcher |
| `git_change_trigger.py` | `GitChangeTrigger` | Dispara acciones en cambios de git |
| `automation_manager.py` | `AutomationManager` | Define y ejecuta flujos de automatización |
| `automation_executor.py` | `AutomationExecutor` | Ejecuta acciones de automatización con retry |
| `task_scheduler.py` | `TaskScheduler` | Scheduler de tareas periódicas |
| `task_models.py` | Dataclasses | `Task`, `TaskResult`, `AutomationFlow` |
| `confirmation_manager.py` | `ConfirmationManager` | Gate de confirmación para operaciones destructivas |
| `permission_profiles.py` | Constantes | Perfiles de permisos por tipo de herramienta |
| `retry_policy.py` | `RetryPolicy` | Backoff exponencial; `DEFAULT_POLICY`, `NETWORK_POLICY` |
| `loop_detector.py` | `LoopDetector` | Detecta bucles infinitos en ejecución de herramientas |
| `heartbeat.py` | `Heartbeat` | Keep-alive para servicios de larga ejecución |
| `cicd_healer.py` | `CICDHealer` | Analiza y repara pipelines CI/CD rotos |
| `webhook_manager.py` | `WebhookManager` | Gestiona endpoints de webhook entrantes/salientes |
| `metrics_database.py` | `MetricsDatabase` | Persiste métricas de ejecución en SQLite |
| `gpu_aware_rate_limiter.py` | `GPUAwareRateLimiter` | Rate limiting que considera disponibilidad de GPU |
| `concurrent_rate_limiter.py` | `ConcurrentRateLimiter` | Rate limiting por concurrencia máxima |
| `execution_bridge.py` | `ExecutionBridge` | Puente sync/async para llamadas a herramientas |
| `execution_plan.py` | `ExecutionPlan` | Plan de ejecución de múltiples herramientas |
| `multi_agent_orchestrator.py` | `MultiAgentOrchestrator` | Orquesta múltiples agentes en paralelo |

## Sub-paquete `db/`

| Archivo | Responsabilidad |
|---------|----------------|
| `base_model.py` | `Base(DeclarativeBase)` de SQLAlchemy 2.0 |
| `engine.py` | `make_async_engine()`, `make_session_factory()` |
| `sqlite_manager.py` | `AsyncDatabaseManager` — wrapper de `async_sessionmaker[AsyncSession]` |

## RetryPolicy

```python
from backend.utils.core.system.retry_policy import DEFAULT_POLICY, NETWORK_POLICY

# Sync
result = DEFAULT_POLICY.execute(lambda: risky_operation())

# Async
result = await NETWORK_POLICY.aexecute(async_network_call)

# Personalizado
policy = RetryPolicy(max_attempts=5, base_delay=1.0, backoff_factor=2.0)
```

## TriggerManager

Único punto de entrada para todos los tipos de triggers (reemplaza `advanced_trigger_manager.py` eliminado):

```python
manager = get_trigger_manager()

# Crear trigger
trigger_id = manager.create_trigger(
    name="auto_test",
    trigger_type="git_push",
    conditions=[{"operator": "eq", "field": "branch", "value": "main"}],
    actions=[{"type": "run_tests"}]
)

manager.evaluate_triggers(event={"type": "git_push", "branch": "main"})
```

## ConfirmationManager

Todas las herramientas destructivas (`write_file`, `run_command`, `delete_file`) deben pasar por aquí:

```python
cm = ConfirmationManager()
approved = cm.request_confirmation(
    operation="delete_file",
    target="src/important.py",
    agent_id="developer_1"
)
```
