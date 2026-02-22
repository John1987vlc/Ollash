# Test Structure - Ollash

## Overview

Los tests han sido reestructurados por módulos para mejorar la organización y modularización.

## Estructura de carpetas

```
tests/
├── test_main.py                 # Test principal que ejecuta todos los tests
├── conftest.py                  # Fixtures compartidas (pytest)
│
├── agents/                      # Tests del módulo agents/
│   ├── __init__.py
│   └── test_auto_agent.py
│
├── core/                        # Tests del módulo core/ (utilities)
│   ├── __init__.py
│   ├── test_llm_response_parser.py   # Tests para LLMResponseParser
│   ├── test_file_validator.py        # Tests para FileValidator
│   └── test_heartbeat.py             # Tests para Heartbeat
│
├── services/                    # Tests del módulo services/
│   └── __init__.py
│
├── utils/                       # Tests del módulo utils/
│   └── __init__.py
│
├── web/                         # Tests del módulo web/
│   ├── __init__.py
│   └── test_blueprints.py      # Tests para blueprints (chat, benchmark, common)
│
├── automations/                 # Tests del módulo automations/
│   ├── __init__.py
│   └── test_automations.py     # Tests para notificaciones, scheduler, executor
│
├── integration/                 # Tests de integración
│   └── __init__.py
│
└── e2e/                        # Tests end-to-end
    └── __init__.py
```

## Cómo ejecutar los tests

### Desde la raíz del proyecto
```bash
python -m pytest tests/ -v
```

### Usando los scripts de automatización (ahora en tests/)
```bash
# En Linux/macOS
bash tests/run_tests.sh

# En Windows
tests\run_tests.bat
```

### Ejecutar tests por módulo
```bash
pytest tests/agents/ -v                   # Solo tests de agents
pytest tests/core/ -v                     # Solo tests de core
pytest tests/web/ -v                      # Solo tests de web
pytest tests/automations/ -v              # Solo tests de automations
pytest tests/integration/ -v              # Solo tests de integración
pytest tests/e2e/ -v                      # Solo tests end-to-end
```

### Ejecutar tests específicos dentro de un módulo
```bash
pytest tests/core/test_file_validator.py -v          # FileValidator
pytest tests/core/test_llm_response_parser.py -v     # LLMResponseParser
pytest tests/web/test_blueprints.py::TestChatBlueprint -v  # Clase específica
```

### Opciones útiles de pytest
```bash
pytest tests/ -v --tb=short               # Traceback corto
pytest tests/ -v --tb=no                  # Sin traceback
pytest tests/ -k "test_valid"              # Solo tests que coincidan con "test_valid"
pytest tests/ --co -q                     # Listar tests sin ejecutar
pytest tests/ -x                          # Parar en el primer error
pytest tests/ --maxfail=3                 # Parar después de 3 fallos
```

## Beneficios de la nueva estructura

✅ **Modularización**: Cada módulo tiene sus propios tests  
✅ **Fácil de mantener**: Cambios en un módulo = tests claros a actualizar  
✅ **Escalabilidad**: Fácil agregar nuevos módulos y tests  
✅ **Organización clara**: Navegar entre tests es intuitivo  
✅ **Ejecución selectiva**: Ejecutar solo lo que necesitas  

## Archivos movidos y reorganizados

| Archivo anterior | Nuevo archivo | Módulo |
|-----------------|--------------|--------|
| test_auto_agent.py | agents/test_auto_agent.py | agents |
| test_core_utilities.py (LLMResponseParser) | core/test_llm_response_parser.py | core |
| test_core_utilities.py (FileValidator) | core/test_file_validator.py | core |
| test_core_utilities.py (Heartbeat) | core/test_heartbeat.py | core |
| test_web.py | web/test_blueprints.py | web |
| test_automations.py | automations/test_automations.py | automations |

## Notas

- La carpeta `tests/` en la raíz mantiene los archivos `conftest.py`, `pytest.ini` y otros archivos globales de configuración
- Cada subcarpeta de módulo tiene su propio `__init__.py` para que pytest las reconozca como paquetes
- El archivo `test_main.py` actúa como documentación y punto de entrada para la suite completa
- Los tests existentes en `unit/`, `integration/` y `e2e/` pueden seguir en esas carpetas o reorganizarse según sea necesario
