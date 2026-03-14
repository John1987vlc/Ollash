# backend/agents/auto_agent_phases/

Implementaciones individuales de cada fase del pipeline `AutoAgent`. Cada fase hereda de `BasePhase` (`base_phase.py`) e implementa el método `run()`.

## Archivos de infraestructura

| Archivo | Responsabilidad |
|---------|----------------|
| `base_phase.py` | Clase abstracta `BasePhase` / `IAgentPhase`; define `run()`, `REQUIRED_TOOLS` |
| `phase_context.py` | Singleton `PhaseContext`: estado compartido entre fases (LLM manager, file manager, generators) |
| `phase_groups.py` | Listas de fases por tier (`FULL_PHASES`, `SLIM_PHASES`, `NANO_PHASES`) |
| `phase_helpers.py` | Helpers compartidos: `get_type_info_if_active()`, `filter_structure_by_type()` |
| `nano_task_expander.py` | Expande tareas comprimidas para modelos nano |

## Secuencia de fases (tier Full)

```
1.  ReadmeGenerationPhase        — genera README inicial, detecta tipo de proyecto
2.  StructureGenerationPhase     — genera árbol de directorios/archivos
3.  LogicPlanningPhase           — crea planes de lógica por archivo
4.  StructurePreReviewPhase      — revisa la estructura antes de crear archivos
5.  EmptyFileScaffoldingPhase    — crea archivos vacíos según estructura
6.  FileContentGenerationPhase   — rellena archivos con código (usa RAG + plan)
7.  FileRefinementPhase          — refina código generado
8.  JavaScriptOptimizationPhase  — optimiza JS/TS específicamente
9.  VerificationPhase            — verifica coherencia de archivos generados
10. CodeQuarantinePhase          — aisla código problemático
11. SecurityScanPhase            — escaneo de vulnerabilidades
12. LicenseCompliancePhase       — verifica licencias de dependencias
13. DependencyReconciliationPhase — reconcilia dependencias declaradas vs. usadas
14. TestGenerationExecutionPhase — genera y ejecuta tests
15. InfrastructureGenerationPhase — genera Dockerfile, CI/CD, configs de infra
16. ExhaustiveReviewRepairPhase  — revisión exhaustiva y reparación
17. FinalReviewPhase             — revisión final del proyecto completo
18. CICDHealingPhase             — sana pipelines CI/CD
19. DocumentationDeployPhase     — despliega documentación generada
20. IterativeImprovementPhase    — itera mejoras según feedback
21. DynamicDocumentationPhase    — genera docs dinámicos
22. ContentCompletenessPhase     — verifica completitud del contenido
23. SeniorReviewPhase            — revisión de nivel senior
```

### Fases opcionales / especiales

| Fase | Cuándo activa |
|------|--------------|
| `ClarificationPhase` | Solo Full/Slim; pide aclaraciones al usuario |
| `PlanValidationPhase` | Solo Full/Slim; valida plan antes de generar |
| `ApiContractPhase` | Solo Full/Slim; define contratos de API |
| `TestPlanningPhase` | Solo Full/Slim; planifica estrategia de tests |
| `ComponentTreePhase` | Solo Full/Slim; genera árbol de componentes |
| `ViabilityEstimatorPhase` | Estima viabilidad del proyecto |
| `ChaosInjectionPhase` | Inyecta errores para probar resiliencia |
| `WebSmokeTestPhase` | Smoke test de la app web generada |
| `ProjectAnalysisPhase` | Analiza proyecto existente para mejorarlo |
| `InterfaceScaffoldingPhase` | Genera interfaces/ABCs |
| `DependencyPrecheckPhase` | Precomprueba dependencias disponibles |
| `GenerationExecutionPhase` | Fase de ejecución de generación alternativa |

## PhaseContext

Singleton que viaja por todas las fases. Campos clave:

```python
ctx.llm_manager          # LLMClientManager — acceso a modelos
ctx.file_manager         # FileManager — lectura/escritura de archivos
ctx.project_name         # Nombre del proyecto en generación
ctx.project_root         # Ruta raíz del proyecto
ctx.project_type_info    # ProjectTypeInfo — tipo detectado, extensiones permitidas
ctx.logic_plans          # Dict[str, str] — planes de lógica por archivo
ctx.structure            # Dict — árbol de estructura generado
ctx.readme_content       # Contenido del README generado
ctx.error_knowledge_base # ErrorKnowledgeBase — patrones de errores aprendidos
ctx.episodic_memory      # EpisodicMemory — memoria episódica cross-proyecto
```

## Convenciones para nuevas fases

1. Heredar de `BasePhase`
2. Implementar `run(ctx: PhaseContext) -> None`
3. Declarar `REQUIRED_TOOLS: list[str]` con las herramientas necesarias
4. Registrar en `phase_groups.py` en el tier correcto
5. Tests en `tests/unit/backend/agents/auto_agent_phases/`
