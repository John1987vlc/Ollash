# backend/utils/domains/

Herramientas organizadas por dominio funcional. Cada sub-paquete contiene implementaciones de herramientas registradas con `@ollash_tool`. El `ToolRegistry` las auto-descubre en startup.

## Sub-paquetes

| Directorio | Toolset ID | Herramientas principales |
|-----------|-----------|--------------------------|
| `auto_generation/` | `auto_generation` | Generación de proyectos, código, tests, estructura |
| `code/` | `code_tools` | Análisis estático, refactoring, formateo |
| `command_line/` | `command_line_tools` | Ejecución de comandos shell, scripts |
| `cybersecurity/` | `cybersecurity_tools` | Escaneo de vulnerabilidades, auditoría |
| `git/` | `git_tools` | Git: status, diff, commit, branch, PR |
| `multimedia/` | `multimedia_tools` | Generación de imágenes, diagramas |
| `network/` | `network_tools` | HTTP requests, web scraping, DNS |
| `orchestration/` | `orchestration_tools` | Coordinación multi-agente |
| `planning/` | `planning_tools` | Planificación de tareas, estimación |
| `system/` | `system_tools` | Info del sistema, procesos, recursos |
| `bonus/` | `bonus_tools` | Herramientas experimentales/extra |

## auto_generation/

El sub-paquete más grande (75+ archivos). Organizado en 4 sub-paquetes:

```
auto_generation/
├── generation/    → structure_generator, enhanced_file_content_generator, infra_generator, multi_language_test_generator
├── planning/      → project_planner, improvement_planner, contingency_planner, analysis_state_manager
├── review/        → project_reviewer, structure_pre_reviewer, senior_reviewer, quality_gate
└── utilities/     → code_patcher, project_type_detector, tech_stack_detector, sandbox_validator, signature_extractor
```

Los imports desde rutas antiguas (shims) siguen funcionando — ver [auto_generation/README.md](auto_generation/README.md).

## Añadir una herramienta nueva

1. Crear archivo en `backend/utils/domains/{dominio}/{nombre}_tool.py`
2. Decorar con `@ollash_tool(...)` — ver [../core/tools/README.md](../core/tools/README.md)
3. El `ToolRegistry` la detecta automáticamente al siguiente inicio
4. Crear test en `tests/unit/backend/utils/domains/{dominio}/test_{nombre}_tool.py`
