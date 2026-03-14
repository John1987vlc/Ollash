# backend/utils/core/

Utilidades transversales del backend. Divididas en 5 sub-paquetes semánticos más archivos planos de uso general.

## Archivos planos

| Archivo | Responsabilidad |
|---------|----------------|
| `constants.py` | Constantes globales del proyecto |
| `exceptions.py` | Excepciones personalizadas del dominio |
| `language_utils.py` | `LanguageUtils`: `infer_language()`, `group_files_by_language()`, `get_test_file_path()` |
| `command_executor.py` | Ejecución de comandos shell con niveles de sandbox |
| `cascade_summarizer.py` | Resumidor en cascada para contextos muy largos |
| `preference_manager_extended.py` | Sistema de preferencias; incluye `migrate_preferences()` |
| `plugin_interface.py` | Interfaz base para el sistema de plugins |

## Sub-paquetes

| Directorio | Área | Descripción |
|-----------|------|-------------|
| `analysis/` | Análisis de código | Quarantine, dependency graph, RAG, vulnerability scanner, validators |
| `io/` | Entrada/Salida | FileManager, CheckpointManager, GitManager, ArtifactManager, ingestion |
| `llm/` | Capa LLM | OllamaClient, PromptLoader, token tracking, parallel generation |
| `memory/` | Sistemas de memoria | EpisodicMemory, ErrorKnowledgeBase, FragmentCache, SQLiteVectorStore |
| `system/` | Sistema | Logger, alertas, automatizaciones, CI/CD healer, trigger manager, DB |
| `tools/` | Sistema de herramientas | ToolRegistry, decorador `@ollash_tool`, sandboxes, executor |

## LanguageUtils

```python
lang = LanguageUtils.infer_language("main.py")           # → "python"
groups = LanguageUtils.group_files_by_language(file_list) # → {"python": [...], "js": [...]}
test_path = LanguageUtils.get_test_file_path("src/foo.py") # → "tests/unit/test_foo.py"
```

## CommandExecutor + Sandbox levels

Los niveles de sandbox se configuran en `backend/config/tool_settings.json`:
- `0` = sin sandbox (solo desarrollo local)
- `1` = restricciones de red
- `2` = filesystem restringido
- `3` = sandbox completo (aislamiento máximo)
