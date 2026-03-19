# backend/utils/domains/auto_generation/

Motor de generación de proyectos completos. Usado principalmente por `AutoAgent` y sus fases. Organizado en 4 sub-paquetes semánticos con shims de compatibilidad en la raíz.

## Sub-paquetes

### `generation/` — Generadores de contenido

| Archivo | Clase | Responsabilidad |
|---------|-------|----------------|
| `enhanced_file_content_generator.py` | `EnhancedFileContentGenerator` | Crea archivos nuevos usando plan de lógica + RAG; clase principal de generación |
| `structure_generator.py` | `StructureGenerator` | Genera árbol de directorios/archivos desde descripción; `filter_structure_by_extensions()` |
| `infra_generator.py` | `InfraGenerator` | Genera Dockerfile, docker-compose, CI/CD configs |
| `multi_language_test_generator.py` | `MultiLanguageTestGenerator` | Genera tests en Python (pytest), JS (vitest), etc. |

### `planning/` — Planificadores

| Archivo | Clase | Responsabilidad |
|---------|-------|----------------|
| `project_planner.py` | `ProjectPlanner` | Plan de alto nivel del proyecto |
| `improvement_planner.py` | `ImprovementPlanner` | Planifica iteraciones de mejora |
| `improvement_suggester.py` | `ImprovementSuggester` | Sugiere mejoras basadas en análisis |
| `contingency_planner.py` | `ContingencyPlanner` | Planes de contingencia para fallos de fases |
| `analysis_state_manager.py` | `AnalysisStateManager` | Gestiona estado de análisis incremental |

### `review/` — Revisores

| Archivo | Clase | Responsabilidad |
|---------|-------|----------------|
| `project_reviewer.py` | `ProjectReviewer` | Revisión completa del proyecto generado |
| `structure_pre_reviewer.py` | `StructurePreReviewer` | Revisa estructura antes de generar archivos |
| `senior_reviewer.py` | `SeniorReviewer` | Revisión nivel senior con feedback detallado |
| `file_completeness_checker.py` | `FileCompletenessChecker` | Verifica que los archivos tienen contenido completo |
| `quality_gate.py` | `QualityGate` | Gate de calidad: bloquea si métricas no cumplen umbral |

### `utilities/` — Utilidades

| Archivo | Clase | Responsabilidad |
|---------|-------|----------------|
| `code_patcher.py` | `CodePatcher` | Edita archivos existentes; `apply_search_replace` (batch) + `apply_unique_edit` (unicidad validada, retorna diff); `_check_brace_balance()` revierte parches que rompan el balance de llaves/corchetes |
| `project_type_detector.py` | `ProjectTypeDetector` | Detecta tipo de proyecto (zero LLM calls, regex keywords) |
| `tech_stack_detector.py` | `TechStackDetector` | Detecta stack tecnológico de un proyecto |
| `sandbox_validator.py` | `SandboxValidator` | Valida código en sandbox antes de escribir |
| `auto_test_generator.py` | `AutoTestGenerator` | Genera tests unitarios automáticamente |
| `file_refiner.py` | `FileRefiner` | Refina código existente preservando lógica |
| `signature_extractor.py` | `extract_signatures()` | Extrae firmas de funciones/clases por extensión |
| `prompt_templates.py` | `PromptTemplates` | Templates de prompts específicos de auto_generation |

## EnhancedFileContentGenerator

Clase principal de generación de archivos:

```python
generator = EnhancedFileContentGenerator(llm_manager, file_manager)

content = generator.generate_file(
    file_path="src/auth.py",
    logic_plan="Implementar JWT authentication...",
    project_context=ctx,
    rag_context=["similar auth implementations..."]
)
```

## CodePatcher

Edita archivos existentes sin sobreescribir si no es necesario.

### `apply_search_replace` — Batch patches (pipeline AutoAgent)

```python
patches = CodePatcher.parse_search_replace_patch(llm_output)
new_content, failed = patcher.apply_search_replace(content, patches, file_ext=".py")
```

Aplica bloques `<<<SEARCH>>> / <<<REPLACE>>> / <<<END>>>`. Falla silenciosamente si el SEARCH no se encuentra (adecuado para salida LLM en pipelines).

`file_ext` (opcional): si se pasa, activa `_check_brace_balance()` tras aplicar todos los parches — revierte al contenido original si detecta un desequilibrio de llaves/corchetes mayor a 5 (tolerancia para strings multilínea y comentarios).

### `apply_unique_edit` — Edición quirúrgica (Interactive Coding Mode)

```python
new_content, diff_lines = patcher.apply_unique_edit(
    file_content=content,
    old_string="def greet(name):\n    return f'Hello, {name}'",
    new_string="def greet(name):\n    return f'Hi, {name}!'",
    file_ext=".py",  # opcional: activa balance check post-edición
)
```

- **Valida unicidad**: lanza `ValueError` si `old_string` aparece 0 o más de 1 vez
- **Normaliza whitespace**: intenta matching con `textwrap.dedent` si el exacto falla
- **Retorna diff**: lista de líneas `unified_diff` lista para mostrar como preview
- **Balance guard**: si `file_ext` se pasa, revierte automáticamente si el resultado rompe el balance de `{}`, `()`, `[]` más allá de la tolerancia
- **No escribe al disco**: el llamador decide si persistir

Usa `difflib.SequenceMatcher` en `_smart_merge` — **NO** heurísticas de longitud o llaves.

## ProjectTypeDetector

```python
detector = ProjectTypeDetector()
info = detector.detect("src/")

# info.project_type         → "web_app", "cli_tool", "api", "library", etc.
# info.allowed_extensions   → frozenset({".py", ".html", ".css", ...})
# info.detected_keywords    → ["flask", "jinja2"]
# info.confidence           → 0.75 (umbral mínimo: 0.10)
```

## Shims de compatibilidad

Los imports desde la ruta plana antigua siguen funcionando:

```python
# Antiguo (sigue funcionando via shim):
from backend.utils.domains.auto_generation.code_patcher import CodePatcher

# Nuevo (path canónico):
from backend.utils.domains.auto_generation.utilities.code_patcher import CodePatcher
```
