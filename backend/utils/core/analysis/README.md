# backend/utils/core/analysis/

Herramientas de análisis de código: quarantine, grafos de dependencias, RAG, escaneo de vulnerabilidades y validadores por lenguaje.

## Archivos principales

| Archivo | Clase | Responsabilidad |
|---------|-------|----------------|
| `code_quarantine.py` | `CodeQuarantine` | Aísla archivos problemáticos en `.quarantine/`; permite restauración |
| `dependency_graph.py` | `DependencyGraph` | Construye grafo de dependencias entre módulos del proyecto |
| `vulnerability_scanner.py` | `VulnerabilityScanner` | Detecta patrones de vulnerabilidades (OWASP Top 10) en código |
| `file_validator.py` | `FileValidator` | Valida sintaxis de archivos según su extensión |
| `shadow_evaluator.py` | `ShadowEvaluator` | Evalúa código en "sombra" sin ejecutarlo en producción |
| `code_analyzer.py` | `CodeAnalyzer` | Análisis estático: complejidad, métricas, code smells |
| `context_distiller.py` | `ContextDistiller` | Destila contexto relevante del proyecto para prompts LLM |
| `cost_analyzer.py` | `CostAnalyzer` | Estima costes de tokens y tiempo de ejecución |
| `critic_loop.py` | `CriticLoop` | Bucle crítico LLM-sobre-LLM para validación |
| `license_checker.py` | `LicenseChecker` | Verifica licencias de dependencias |
| `chaos_injector.py` | `ChaosInjector` | Inyecta errores controlados para probar resiliencia |
| `input_validators.py` | Funciones | Validación de entradas en boundaries del sistema |

## Sub-paquetes

### `scanners/`

| Archivo | Responsabilidad |
|---------|----------------|
| `rag_context_selector.py` | `RAGContextSelector`: búsqueda semántica en código del proyecto vía `SQLiteVectorStore` |
| `dependency_scanner.py` | `DependencyScanner`: escanea `requirements.txt`, `package.json`, etc. |
| `dependency_reconciler.py` | `DependencyReconciler`: reconcilia dependencias declaradas vs. importadas en código |

### `validators/`

Validadores de sintaxis por lenguaje. Todos heredan de `BaseValidator`:

| Archivo | Lenguaje(s) |
|---------|------------|
| `python_validator.py` | `.py` — `ast.parse()` |
| `javascript_validator.py` | `.js`, `.jsx` — regex + heurísticas |
| `typescript_validator.py` | `.ts`, `.tsx` — regex + heurísticas |
| `json_validator.py` | `.json` — `json.loads()` |
| `yaml_validator.py` | `.yaml`, `.yml` — `yaml.safe_load()` |
| `default_validator.py` | Cualquier extensión no reconocida |

## RAGContextSelector

Usa `SQLiteVectorStore` (sin ChromaDB) para búsqueda semántica:

```python
selector = RAGContextSelector(project_root)
context = selector.get_relevant_context(
    query="función de autenticación",
    max_results=5
)
# → List[str] con fragmentos de código relevantes
```

## CodeQuarantine

```python
quarantine = CodeQuarantine(project_root)
quarantine.quarantine_file("src/bad_file.py", reason="syntax error")
quarantine.restore_file("src/bad_file.py")
quarantine.list_quarantined()  # → List[QuarantinedFile]
```
