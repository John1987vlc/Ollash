![Local IT Agent - Ollash Logo](Ollash.png)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
# Local IT Agent - Ollash - Asistente de Código y TI con Ollama

Local IT Agent - Ollash es un asistente basado en el modelo de lenguaje Ollama, diseñado para ayudar en tareas de desarrollo de software como análisis de código, generación de prototipos y investigación web. Su arquitectura modular basada en "Tool Calling" le permite interactuar con diversas herramientas y ejecutar acciones, siendo fácilmente extensible a otras áreas de la informática como sistemas, redes y ciberseguridad.

## Características Principales
*   **Arquitectura Modular con "Tool Calling":** Utiliza un enfoque de "Tool Calling" para interactuar con herramientas del sistema y APIs, permitiendo una gran flexibilidad y extensibilidad.

## Nuevas Características

*   **Detección de Bucles Inteligente:** El agente ahora incluye un mecanismo de detección de bucles que identifica secuencias de acciones repetitivas que no conducen a progreso. Si se detecta un bucle (actualmente, 3 llamadas idénticas consecutivas a la misma herramienta con los mismos argumentos y resultados), el agente activa una "compuerta humana" (`require_human_gate`) para solicitar intervención del usuario, evitando así ciclos infinitos y el consumo innecesario de recursos. Esta funcionalidad mejora la robustez y la interactividad del agente.

## Nuevas Características de Rendimiento y Eficiencia

*   **Metascore de "Calidad por Segundo" en Benchmarking:** Se ha añadido una nueva métrica (`tokens_per_second`) en los benchmarks para medir la agilidad de los modelos, relacionando la cantidad de tokens generados con el tiempo total.
*   **Test de Estrés de Contexto:** Se ha incorporado una nueva prueba en los benchmarks que evalúa el rendimiento de los modelos al procesar archivos de gran tamaño (15,000 líneas), filtrando aquellos que fallan con un contexto amplio.
*   **Sistema de Caching de Razonamiento:** Se ha implementado una base de datos vectorial con `ChromaDB` para cachear soluciones a errores previos. Si el agente encuentra un error similar a uno ya resuelto (con una similitud > 95%), reutiliza la solución anterior, ahorrando tiempo y tokens.
*   **Modo de Ejecución Pre-Validada (Dry Run):** Antes de ejecutar comandos, el sistema ahora realiza una pre-validación para detectar errores de sintaxis comunes (ej. `pyton` en lugar de `python`), evitando ciclos de error innecesarios.
*   **Checkpoints de Estado en Modo Autónomo:** El agente ahora crea "snapshots" del estado del proyecto usando `git` después de cada operación que modifica el estado (ej. `write_file`). Esto permite usar la nueva herramienta `rollback_to_last_checkpoint` para revertir a un estado estable en caso de un error catastrófico.
*   **Orquestación por Capas para Errores:** Al encontrar un error, el agente primero intenta solucionarlo con un modelo pequeño y rápido (`self_correction_model`). Si la confianza en la solución es baja, escala el problema a un modelo más grande y potente (`reasoning_model`), optimizando el uso de recursos.
*   **Carga Perezosa (Lazy Loading) de Herramientas:** Las herramientas de los diferentes dominios ya no se cargan al inicio, sino que se instancian dinámicamente solo cuando son necesarias, reduciendo significativamente el tiempo de arranque de la aplicación.

*   **Agente Principal (`DefaultAgent`):** Es el agente central que orquesta la interacción con el modelo de lenguaje (Ollama) y delega tareas a agentes especializados. Se encarga de la lógica principal, la detección de bucles y la gestión general de la sesión.
### Herramientas de Dominio (`src/utils/domains`)

Este conjunto de herramientas se organiza por dominios, permitiendo que el agente se especialice en diferentes tipos de tareas:

*   **ORQUESTACIÓN Y PLANIFICACIÓN (`PlanningTools`, `OrchestrationTools`):**
    *   `PlanningTools`: Módulo dedicado a la creación y visualización de planes de acción paso a paso, crucial para abordar tareas complejas de forma estructurada.
    *   `evaluate_plan_risk`: Evalúa planes de acción detectando riesgos técnicos, de seguridad e impacto.
    *   `detect_user_intent`: Clasifica la intención del usuario (ej. exploración, depuración, cambio en producción).
    *   `require_human_gate`: Marca acciones críticas para requerir aprobación humana explícita.
    *   `summarize_session_state`: Resume el estado actual de la sesión, cambios y decisiones.
    *   `explain_decision`: Explica las razones detrás de las decisiones del agente y alternativas descartadas.
    *   `validate_environment_expectations`: Verifica si el entorno actual cumple con las expectativas (OS, versión, permisos, red).
    *   `detect_configuration_drift`: Detecta desviaciones en la configuración del sistema respecto a una línea base.
    *   `evaluate_compliance`: Evalúa configuraciones y prácticas del sistema frente a un estándar de cumplimiento.
    *   `generate_audit_report`: Genera informes estructurados a partir de resultados de herramientas.
    *   `propose_governance_policy`: Propone nuevas políticas de gobernanza basadas en brechas de cumplimiento.

*   **CÓDIGO / SOFTWARE ENGINEERING (`FileSystemTools`, `CodeAnalysisTools`, `AdvancedCodeTools`):**
    *   `FileSystemTools`: Encapsula todas las operaciones relacionadas con el sistema de archivos, incluyendo leer, escribir, borrar, listar directorios, calcular diferencias entre archivos y resumir su contenido.
    *   `CodeAnalysisTools`: Provee funcionalidades para analizar la estructura del proyecto, identificar dependencias, evaluar la calidad del código y buscar patrones específicos dentro del código fuente. Es fundamental para tareas de desarrollo y depuración.
    *   `detect_code_smells`: Analiza el código en busca de "malos olores" (ej. funciones largas, duplicación).
    *   `suggest_refactor`: Propone refactorizaciones concretas, indicando beneficios y riesgos.
    *   `map_code_dependencies`: Construye un mapa lógico de dependencias entre módulos o paquetes.
    *   `compare_configs`: Compara archivos de configuración y detecta diferencias semánticas.

*   **LÍNEA DE COMANDOS (`CommandLineTools`):**
    *   `CommandLineTools`: Permite la ejecución controlada de comandos de shell, correr tests unitarios (utilizando pytest) y validar cambios (ejecutando tests y linters) antes de integrar código. Esto es clave para la automatización de tareas.

*   **OPERACIONES GIT (`GitOperationsTools`):**
    *   `GitOperationsTools`: Ofrece capacidades para interactuar con repositorios Git, como consultar el estado (status), realizar commits y enviar cambios a repositorios remotos (push).

*   **RED / INFRA (`NetworkTools`, `AdvancedNetworkTools`):**
    *   `NetworkTools`: Herramientas básicas para diagnósticos de red como ping y traceroute.
    *   `analyze_network_latency`: Correlaciona latencia, pérdida de paquetes y rutas de red.
    *   `detect_unexpected_services`: Detecta servicios escuchando en puertos no esperados.
    *   `map_internal_network`: Descubre hosts, roles probables y relaciones en la red local.

*   **SISTEMA / OPERACIONES (`SystemTools`, `AdvancedSystemTools`):**
    *   `SystemTools`: Herramientas para obtener información del sistema, listar procesos, instalar paquetes, y leer archivos de log.
    *   `check_disk_health`: Analiza el uso del disco, inodos, crecimiento anómalo y directorios sospechosos.
    *   `monitor_resource_spikes`: Detecta picos en CPU, RAM o I/O y los correlaciona con procesos.
    *   `analyze_startup_services`: Lista servicios de inicio y evalúa su necesidad.
    *   `rollback_last_change`: Revierte el último cambio conocido (git, config, paquete) de forma controlada.

*   **CIBERSEGURIDAD (`CybersecurityTools`, `AdvancedCybersecurityTools`):**
    *   `CybersecurityTools`: Herramientas para escanear puertos, verificar hashes de archivos, analizar logs de seguridad y recomendar hardening.
    *   `assess_attack_surface`: Evalúa la superficie de ataque combinando puertos, servicios, usuarios y configuraciones.
    *   `detect_ioc`: Busca Indicadores de Compromiso (IOCs) en logs, procesos y archivos.
    *   `analyze_permissions`: Audita permisos de archivos, usuarios y servicios en busca de excesos.
    *   `security_posture_score`: Calcula una puntuación de postura de seguridad con explicación.

*   **BONUS (`BonusTools`):**
    *   `analyze_sentiment`: Analiza el sentimiento de un texto dado.
    *   `generate_creative_content`: Genera contenido de texto creativo basado en un prompt y estilo.
    *   `translate_text`: Traduce texto de un idioma a otro.

*   **Utilidades del Core (`src/utils/core`):** Módulos fundamentales que soportan a las herramientas especializadas y la lógica del agente.
    *   `AgentLogger`: Sistema de logging mejorado con salida a consola coloreada y archivos.
    *   `TokenTracker`: Monitoreo del consumo de tokens en las interacciones con el LLM.
    *   `FileManager`: Gestión básica de archivos y directorios.
    *   `CommandExecutor`: Ejecución segura y controlada de comandos externos, con niveles de sandboxing.
    *   `GitManager`: Funcionalidades básicas para interactuar con Git a bajo nivel.
    *   `CodeAnalyzer`: Análisis estático de código para extraer información clave.
    *   `ToolExecutor`: Abstracción para la gestión y ejecución de herramientas, incluyendo la lógica de confirmación del usuario.
    *   `all_tool_definitions`: Definiciones de todas las herramientas disponibles para el agente.

## Tecnologías Utilizadas

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white)
![VSCode](https://img.shields.io/badge/VSCode-007ACC?style=for-the-badge&logo=visual-studio-code&logoColor=white)
![Local Development](https://img.shields.io/badge/Local%20Development-Offline-blue?style=for-the-badge&logo=offline-pages&logoColor=white)

*   **Python 3:** Lenguaje de programación principal del agente.
*   **Ollama:** Plataforma para ejecutar modelos de lenguaje grandes de forma local, permitiendo mayor privacidad y control.
*   **`qwen3-coder-next`:** Modelo de lenguaje específico utilizado por el agente para tareas de código.
*   **`requests`:** Biblioteca HTTP para Python, usada para interactuar con la API de Ollama.
*   **`pytest`:** Framework de testing para Python, esencial para asegurar la calidad del código y la funcionalidad de las herramientas.
*   **`colorama`:** Para mejorar la legibilidad de la salida de la consola con colores.

## Estructura del Proyecto

```
local-it-agent-ollash/
├── assets/                  # Archivos estáticos (ej. index.html para prototipos)
├── config/                  # Archivos de configuración (ej. settings.json)
├── docs/                    # Documentación del proyecto
├── logs/                    # Archivos de registro de la ejecución del agente
├── scripts/                 # Scripts de inicio rápido (ej. .bat, .ps1)
├── src/                     # Código fuente principal
│   ├── agents/              # Implementación del agente principal (DefaultAgent)
│   │   └── default_agent.py
│   ├── cli/                 # Interfaz de línea de comandos
│   │   └── asistente_ollama.py
│   └── utils/               # Utilidades comunes y módulos de herramientas especializados
│       ├── core/            # Módulos centrales y genéricos (FileManager, CommandExecutor, etc.)
│       └── domains/         # Módulos de herramientas especializados por dominio
│           ├── bonus/
│           ├── code/
│           ├── command_line/
│           ├── cybersecurity/
│           ├── git/
│           ├── network/
│           ├── orchestration/
│           ├── planning/
│           └── system/
├── tests/                   # Pruebas unitarias
├── venv/                    # Entorno virtual de Python
├── .agent_memory.json       # Memoria del agente
├── GEMINI.md                # Documentación para el agente Gemini
├── pyproject.toml           # Configuración del proyecto y dependencias (PEP 518)
├── pytest.ini               # Configuración de Pytest
├── README.md                # Este archivo
├── requirements-dev.txt     # Dependencias de desarrollo
├── requirements.txt         # Dependencias del proyecto
└── run_agent.py             # Punto de entrada principal para ejecutar el agente
```

## Instalación

Sigue estos pasos para configurar y ejecutar Local IT Agent - Ollash en tu entorno local:

### 1. Clona el Repositorio

```bash
git clone <URL_DEL_REPOSITORIO>
cd local-it-agent-ollash
```

### 2. Crea y Activa un Entorno Virtual

Es altamente recomendable usar un entorno virtual para gestionar las dependencias:

```bash
python -m venv venv
# En Windows:
.\venv\Scripts\activate
# En macOS/Linux:
source venv/bin/activate
```

### 3. Instala las Dependencias

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Configura Ollama

Asegúrate de tener [Ollama](https://ollama.ai/) instalado y en funcionamiento. Luego, descarga el modelo `qwen3-coder-next`:

```bash
ollama pull qwen3-coder-next
```

Puedes verificar la configuración del modelo en `config/settings.json`.

## Uso

Para iniciar el asistente, ejecuta el siguiente comando:

```bash
python run_agent.py --chat
```

Esto iniciará una sesión de chat donde podrás interactuar con el agente.

## Ejecución de Tests

Para ejecutar las pruebas unitarias del proyecto, asegúrate de tener activado tu entorno virtual y ejecuta `pytest`:

```bash
pytest
```
Hemos añadido 20 nuevos casos de prueba (`tests/test_new_user_cases.py`) para evaluar el comportamiento del agente en diversas situaciones, incluyendo la detección de cuellos de botella y la robustez de la lógica de orquestación. Para estos tests, se recomienda el uso de un modelo más pequeño y eficiente como `llama3.2:latest`.

Puedes ejecutar los tests de integración con el modelo `llama3.2:latest` usando:

```bash
ollama pull llama3.2:latest
python run_agent.py --model llama3.2:latest --chat
# Then interact with the agent or run specific integration tests.
```


## Integración Continua (CI)

El proyecto utiliza GitHub Actions para la integración continua. El workflow `ci.yml` se ejecuta automáticamente en cada `push` o `pull_request` a la rama `master`.

### Funcionalidades del CI:
*   **Instalación de Dependencias:** Configura un entorno Python e instala las dependencias del proyecto (`requirements.txt` y `requirements-dev.txt`).
*   **Ejecución de Tests Unitarios:** Ejecuta los tests unitarios que no requieren una instancia de Ollama en ejecución (`tests/test_code_agent_integration.py`).
*   **Exclusión de Tests de Integración:** Los tests que interactúan con una instancia real de Ollama (`tests/test_ollama_integration.py`) son omitidos en el CI, ya que requieren un entorno específico que no está disponible en GitHub Actions.

Puedes ver la configuración del workflow en: `.github/workflows/ci.yml`

## Configuración

El archivo `config/settings.json` contiene la configuración principal del agente:

```json
{
  "model": "qwen3-coder-next",
  "ollama_url": "http://localhost:11434",
  "timeout": 300,
  "max_tokens": 4096,
  "temperature": 0.5,
  "history_limit": 20,
  "sandbox": "limited",
  "project_root": ".",
  "default_system_prompt_path": "prompts/orchestrator/default_orchestrator.json"
}
```

Puedes modificar estos valores para cambiar el modelo de Ollama, el tiempo de espera o el número máximo de iteraciones.

### Variables de Entorno

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `MOLTBOT_OLLAMA_URL` | URL de Ollama para Docker y runtime | `http://localhost:11434` |
| `OLLAMA_TEST_URL` | URL de Ollama para tests | `http://localhost:11434` |
| `OLLAMA_TEST_TIMEOUT` | Timeout para tests (segundos) | `300` |

Para usar un servidor Ollama remoto en tests:
```bash
OLLAMA_TEST_URL=http://tu-servidor:11434 pytest
```

## Contribución

¡Las contribuciones son bienvenidas! Por favor, abre un issue para discutir nuevas características o mejoras, o envía un pull request.

## Licencia

MIT License