![Local IT Agent - Ollash Logo](Ollash.png)
# Local IT Agent - Ollash - Asistente de Código y TI con Ollama

Local IT Agent - Ollash es un asistente basado en el modelo de lenguaje Ollama, diseñado para ayudar en tareas de desarrollo de software como análisis de código, generación de prototipos y investigación web. Su arquitectura modular basada en "Tool Calling" le permite interactuar con diversas herramientas y ejecutar acciones, siendo fácilmente extensible a otras áreas de la informática como sistemas, redes y ciberseguridad.

## Características Principales

Local IT Agent - Ollash organiza sus funcionalidades en módulos de herramientas especializados para una mayor claridad y mantenibilidad, facilitando su expansión futura a dominios IT más amplios:

*   **Agente Principal (Core Agent):** Centraliza la lógica de interacción con el modelo de lenguaje (Ollama) y la orquestación de las herramientas. Es el cerebro que decide qué acción tomar.
*   **Herramientas de Planificación (`PlanningTools`):** Módulo dedicado a la creación y visualización de planes de acción paso a paso, crucial para abordar tareas complejas de forma estructurada.
*   **Herramientas de Sistema de Archivos (`FileSystemTools`):** Encapsula todas las operaciones relacionadas con el sistema de archivos, incluyendo leer, escribir, borrar, listar directorios, calcular diferencias entre archivos y resumir su contenido.
*   **Herramientas de Análisis de Código (`CodeAnalysisTools`):** Provee funcionalidades para analizar la estructura del proyecto, identificar dependencias, evaluar la calidad del código y buscar patrones específicos dentro del código fuente. Es fundamental para tareas de desarrollo y depuración.
*   **Herramientas de Línea de Comandos (`CommandLineTools`):** Permite la ejecución controlada de comandos de shell, correr tests unitarios (utilizando pytest) y validar cambios (ejecutando tests y linters) antes de integrar código. Esto es clave para la automatización de tareas.
*   **Herramientas de Operaciones Git (`GitOperationsTools`):** Ofrece capacidades para interactuar con repositorios Git, como consultar el estado (status), realizar commits y enviar cambios a repositorios remotos (push).
*   **Utilidades Comunes (Base Utilities):** Incluyen módulos fundamentales que soportan a las herramientas especializadas:
    *   `FileManager`: Gestión básica de archivos y directorios.
    *   `CommandExecutor`: Ejecución segura y controlada de comandos externos, con niveles de sandboxing.
    *   `CodeAnalyzer`: Análisis estático de código para extraer información clave.
    *   `GitManager`: Funcionalidades básicas para interactuar con Git a bajo nivel.
    *   `AgentLogger`: Sistema de logging mejorado con salida a consola coloreada y archivos.
    *   `TokenTracker`: Monitoreo del consumo de tokens en las interacciones con el LLM.
    *   `ToolExecutor`: Abstracción para la gestión y ejecución de herramientas, incluyendo la lógica de confirmación del usuario.

## Tecnologías Utilizadas

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
│   ├── agents/              # Implementación del agente principal (CodeAgent)
│   │   └── code_agent.py
│   ├── cli/                 # Interfaz de línea de comandos
│   │   └── asistente_ollama.py
│   ├── core/                # Lógica central del asistente
│   │   ├── asistente_avanzado_v2.py
│   │   └── asistente_avanzado.py
│   └── utils/               # Utilidades comunes y módulos de herramientas especializados
│       ├── __init__.py
│       ├── agent_logger.py
│       ├── code_analyzer.py
│       ├── code_analysis_tools.py
│       ├── command_executor.py
│       ├── command_line_tools.py
│       ├── file_manager.py
│       ├── file_system_tools.py
│       ├── git_manager.py
│       ├── git_operations_tools.py
│       ├── planning_tools.py
│       ├── token_tracker.py
│       └── tool_interface.py
├── tests/                   # Pruebas unitarias
├── venv/                    # Entorno virtual de Python
├── .agent_memory.json       # Memoria del agente
├── GEMINI.md                # Documentación para el agente Gemini
├── pyproject.toml           # Configuración del proyecto y dependencias (PEP 518)
├── pytest.ini               # Configuración de Pytest
├── README.md                # Este archivo (¡ahora actualizado!)
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

## Configuración

El archivo `config/settings.json` contiene la configuración principal del agente:

```json
{
  "model": "qwen3-coder-next",
  "ollama_url": "http://localhost:11434",
  "system_prompt": "You are Local IT Agent - Ollash, an AI Code Agent. Your goal is to assist the user with their software development tasks and potentially broader IT operations (systems, networks, cybersecurity). Always aim to fulfill the user's request directly and efficiently. If the user asks you to CREATE or MODIFY a file (e.g., 'create an HTML file', 'add a function to a Python file'), your FIRST priority is to use the 'write_file' tool with the complete content. Do NOT use 'list_directory' or 'read_file' repeatedly if the objective is already clear. Use information gathering tools (like 'list_directory', 'read_file', 'search_code', 'analyze_project') ONLY if you genuinely need more context to understand the request, or if the user explicitly asks for information. Avoid repetitive actions or getting stuck in loops. After executing a tool, evaluate its output and determine the next logical step towards fulfilling the user's goal. For actions that modify the project, you will need user confirmation. Respond with clear, concise information in markdown format. Always use relative paths. Think step-by-step.",
  "max_tokens": 4096,
  "temperature": 0.5,
  "history_limit": 20,
  "sandbox": "limited",
  "project_root": "."
}
```

Puedes modificar estos valores para cambiar el modelo de Ollama, el tiempo de espera o el número máximo de iteraciones.

## Contribución

¡Las contribuciones son bienvenidas! Por favor, abre un issue para discutir nuevas características o mejoras, o envía un pull request.

## Licencia

[Especifica tu licencia aquí, por ejemplo: MIT License]
