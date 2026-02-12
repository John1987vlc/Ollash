# Ollash - Agente Local de IT Impulsado por Ollama

![Ollash Logo](Ollash.png)

Ollash es un agente de inteligencia artificial avanzado diseñado para asistir a desarrolladores y profesionales de IT. Aprovecha el poder de los Large Language Models (LLMs) ejecutados localmente a través de la plataforma [Ollama](https://ollama.ai/), permitiendo tanto interacción directa vía CLI como la ejecución autónoma de tareas complejas como la generación de proyectos completos de software.

Este proyecto se distingue por su arquitectura modular, alta mantenibilidad y una profunda observabilidad, fruto de una refactorización estratégica para escalar y adaptarse a las demandas de un entorno de desarrollo en rápida evolución.

---

## ✅ Estado de Calidad

**Todas las pruebas unitarias están pasando exitosamente:**

| Métrica | Resultado |
|---------|-----------|
| **Tests Totales** | 468/468 ✅ |
| **Tasa de Éxito** | 100% |
| **Tests Unitarios** | 331/331 ✅ |
| **Tests de Integración** | 137/137 ✅ |
| **Última Ejecución** | Éxita (0.02.2026) |

El proyecto ha alcanzado una cobertura completa de pruebas con énfasis en:
- Pruebas unitarias de componentes core (kernel, managers, servicios)
- Pruebas de integración de agentes (DefaultAgent, AutoAgent, OllamaIntegration)
- Pruebas end-to-end de casos de uso complejos
- Validación de configuración y esquemas JSON

---

## 🚀 Arquitectura del Sistema (El Corazón de Ollash)

La arquitectura de Ollash ha sido meticulosamente rediseñada para ofrecer una modularidad, extensibilidad y observabilidad excepcionales. En su núcleo, encontramos el **Agent Kernel**, un *singleton* que centraliza la gestión de servicios globales y actúa como el pilar de la estabilidad del sistema.

### **Principios Arquitectónicos Clave:**

*   **Desacoplamiento:** Los componentes interactúan a través de interfaces bien definidas, minimizando las dependencias implícitas.
*   **Responsabilidad Única (SRP):** Cada módulo tiene una función clara y específica.
*   **Extensibilidad:** Facilita la incorporación de nuevas funcionalidades, LLMs o herramientas sin alterar el núcleo.
*   **Observabilidad:** Proporciona una visión profunda del comportamiento del agente y las interacciones del LLM.

### **Componentes Centrales:**

1.  **Agent Kernel (`src/core/kernel.py`):**
    *   El corazón del sistema, implementado como un *singleton* para asegurar una única instancia global.
    *   **ConfigLoader:** Gestiona una configuración modular y validada (ver más abajo).
    *   **StructuredLogger:** Ofrece un sistema de logging JSON con `correlation_id` para trazabilidad de interacciones completas.
    *   Provee acceso centralizado a los servicios globales para todos los agentes.

2.  **Servicios Desacoplados:**
    *   **LLMClientManager (`src/services/llm_manager.py`):** Responsable de aprovisionar y gestionar instancias de `OllamaClient` para diferentes roles de LLM (ej. `coder`, `planner`), encapsulando la lógica de selección de modelos y aplicación de *benchmarks*.
    *   **LLMRecorder (`src/utils/core/llm_recorder.py`):** Registra detalladamente cada interacción con Ollama, incluyendo prompts, respuestas, uso de tokens, latencia y modelo utilizado, facilitando el análisis y debugging de decisiones del LLM.
    *   **ToolSpanManager (`src/utils/core/tool_span_manager.py`):** Implementa un sistema de "spans" para cada ejecución de herramienta, registrando su duración, éxito/fallo y vinculándolo al `correlation_id` global.

3.  **Interfaces (ABCs en `src/interfaces/`):**
    *   **`IModelProvider`:** Contrato para cualquier servicio que provea clientes de LLM, permitiendo su intercambio.
    *   **`IToolExecutor`:** Interfaz para la ejecución de herramientas, desacoplando la lógica de la herramienta de su invocación.
    *   **`IMemorySystem`:** Define cómo los agentes interactúan con el almacenamiento de memoria, ocultando los detalles de implementación subyacentes.
    *   **`IAgentPhase`:** Contrato para cada etapa del pipeline del `AutoAgent`, garantizando una estructura uniforme y extensible.

---

## ✨ Características Principales

### **0. Phase 6: Sistema Avanzado de Notificaciones y Automatización**

**Phase 6** introduce un conjunto poderoso de componentes para mejorar la comunicación, inteligencia y automatización del sistema:

#### **7 Nuevos Managers de Núcleo:**
- **AdaptiveNotificationUI**: Crea artefactos visuales interactivos (diagramas Mermaid, árboles de decisión, tarjetas de métricas)
- **WebhookManager**: Envía notificaciones a Slack, Discord, Teams y webhooks personalizados
- **ActivityReportGenerator**: Genera reportes diarios, análisis de tendencias y detección de anomalías
- **VoiceCommandProcessor**: Convierte comandos de voz en acciones ejecutables
- **MemoryOfDecisions**: Registra decisiones y aprende de resultados para sugerencias inteligentes
- **FeedbackCycleManager**: Extrae preferencias de usuario del feedback para personalización
- **AdvancedTriggerManager**: Crea automatizaciones complejas con lógica AND/OR/NOT/XOR

#### **REST API Completa:**
- 30+ endpoints para exponer toda la funcionalidad de Phase 6
- Integración Flask lista para producción
- Soporte para operaciones por lotes y exportación de datos

#### **Guías y Documentación:**
- `PHASE_6_GETTING_STARTED.md`: Inicio rápido en 15 minutos
- `PHASE_6_API_INTEGRATION.md`: Referencia completa de API con ejemplos
- `PHASE_6_COMPLETION_SUMMARY.md`: Resumen técnico detallado
- `FILE_STRUCTURE_PHASE6.md`: Guía de navegación y arquitectura

**Uso:**
```python
from src.utils.core.webhook_manager import get_webhook_manager, WebhookType
from src.utils.core.voice_command_processor import get_voice_command_processor

# Enviar notificación a Slack
webhooks = get_webhook_manager()
webhooks.register_webhook("slack", WebhookType.SLACK, "https://hooks.slack.com/...")
webhooks.send_to_webhook_sync(message="Alerta del sistema", title="⚠️ Status")

# Procesar comando de voz
voice = get_voice_command_processor()
command = voice.process_voice_input("crear tarea para mañana")
```

---

### **1. Modo Interactivo: `DefaultAgent` (CLI Chat)**

El `DefaultAgent` proporciona una experiencia de chat interactiva en la línea de comandos, actuando como un asistente de IT con capacidades de "tool-calling" y una orquestación inteligente.

*   **Chat basado en Mixins:** Su lógica se descompone en *mixins* reutilizables:
    *   `IntentRoutingMixin`: Clasifica la intención del usuario y selecciona el LLM más adecuado para la tarea (ej. codificación, planificación, análisis).
    *   `ToolLoopMixin`: Gestiona el bucle de ejecución de herramientas, incluyendo "confirmation gates" para acciones que modifican el sistema y detección de bucles infinitos.
    *   `ContextSummarizerMixin`: Maneja automáticamente la ventana de contexto, resumiendo conversaciones extensas para mantener al LLM dentro de sus límites de tokens.
*   **Acceso a un amplio conjunto de herramientas:** El agente puede interactuar con el sistema de archivos, ejecutar comandos de terminal, gestionar repositorios Git, analizar código, y más.
*   **`Correlation ID`:** Cada interacción de chat genera un `correlation_id` único, permitiendo rastrear todas las operaciones relacionadas en los logs estructurados.

**Uso:**
```bash
python run_agent.py --chat
```

### **2. Modo Autónomo: `AutoAgent` (Generación de Proyectos)**

El `AutoAgent` es un orquestador de proyectos que genera aplicaciones completas a partir de una descripción textual, siguiendo un pipeline de fases bien definido y auto-correctivo.

*   **Pipeline Modular de Fases:** El antiguo pipeline monolítico de 8 fases se ha transformado en una secuencia de clases `IAgentPhase` independientes y reutilizables (ej. `ReadmeGenerationPhase`, `StructureGenerationPhase`, `FileContentGenerationPhase`, `TestGenerationExecutionPhase`, `SeniorReviewPhase`).
*   **`PhaseContext`:** Un objeto contextual que encapsula todas las dependencias (loggers, managers, LLMs) para cada fase, simplificando la inyección de dependencias y el mantenimiento.
*   **Ciclos de Verificación y Refinamiento:** Incluye fases de verificación de código, generación y ejecución de tests multi-idioma, y ciclos de mejora iterativa para corregir errores automáticamente.
*   **Revisión de Estructura y Senior:** Incorpora revisiones automatizadas de la estructura inicial y una "revisión de senior" final para asegurar la calidad del proyecto generado.

**Uso:**
```bash
python auto_agent.py --description "Crea una aplicación de lista de tareas con Flask y SQLite" --name task_manager --loops 1
```

### **3. Observabilidad Avanzada y Trazabilidad**

El sistema de observabilidad de Ollash ha sido diseñado para proporcionar una visibilidad sin precedentes en las operaciones del agente, facilitando el debugging y la auditoría.

*   **Structured Logger (`src/utils/core/structured_logger.py`):**
    *   Todos los eventos del sistema se registran en formato JSON, lo que permite un análisis programático y fácil integración con herramientas de monitoreo.
    *   **Correlation IDs:** Cada interacción de usuario o proceso autónomo genera un `correlation_id` que se propaga a todos los logs relacionados, permitiendo reconstruir el flujo completo de una operación.
    *   **Rotación de Logs:** Los logs se gestionan en la carpeta `logs/` con rotación automática para evitar el llenado del disco.
*   **LLM Interaction Recorder (`src/utils/core/llm_recorder.py`):**
    *   Registra cada prompt enviado y cada respuesta recibida de los LLMs de Ollama.
    *   Captura métricas cruciales como uso de tokens, modelo específico, latencia y estado de éxito/error.
*   **Tool Spans (`src/utils/core/tool_span_manager.py`):**
    *   Mide el tiempo de ejecución de cada herramienta (`start_span`, `end_span`).
    *   Registra si la herramienta se ejecutó con éxito o falló, proporcionando detalles relevantes en el log estructurado.

---

## 📁 Estructura de Carpetas

La nueva organización del proyecto refleja la arquitectura modular, haciendo más intuitivo para los desarrolladores localizar y contribuir a funcionalidades específicas.

```
ollash/
├── config/
│   ├── agent_features.json           # Configuración de características y funcionalidades del agente
│   ├── llm_models.json               # Asignaciones de modelos LLM y configuraciones de Ollama
│   └── tool_settings.json            # Configuración de herramientas, logging y parámetros operativos
├── src/
│   ├── agents/
│   │   ├── mixins/                   # Mixins reutilizables para DefaultAgent (IntentRouting, ToolLoop, ContextSummarizer)
│   │   ├── auto_agent_phases/        # Clases de fases independientes para el pipeline de AutoAgent
│   │   └── ...                       # DefaultAgent, AutoAgent y otros agentes
│   ├── core/                         # Componentes fundamentales del Kernel (AgentKernel, ConfigSchemas, StructuredLogger, etc.)
│   │   ├── config_schemas.py         # Definiciones de esquemas Pydantic para la configuración
│   │   ├── kernel.py                 # El Agent Kernel (singleton) y ConfigLoader
│   │   └── structured_logger.py      # Implementación del logger estructurado con JSON y Correlation IDs
│   │   └── ...                       # Otros servicios core (file_manager, command_executor, etc.)
│   ├── interfaces/                   # Definiciones de interfaces (ABCs) para desacoplamiento (IModelProvider, IToolExecutor, IMemorySystem, IAgentPhase)
│   │   ├── iagent_phase.py           # Interfaz para las fases del AutoAgent
│   │   ├── imodel_provider.py        # Interfaz para proveedores de clientes LLM
│   │   ├── imemory_system.py         # Interfaz para sistemas de memoria del agente
│   │   └── itool_executor.py         # Interfaz para ejecutores de herramientas
│   ├── services/                     # Servicios especializados (LLMClientManager)
│   │   └── llm_manager.py            # Gestión de clientes LLM
│   └── utils/
│       ├── core/                     # Utilidades core existentes (agent_logger, ollama_client, llm_recorder, tool_span_manager, etc.)
│       │   ├── agent_logger.py       # Wrapper sobre StructuredLogger
│       │   ├── llm_recorder.py       # Registro detallado de interacciones LLM
│       │   └── tool_span_manager.py  # Gestión de Spans para ejecución de herramientas
│       │   └── ...
│       └── domains/                  # Implementaciones de herramientas y servicios por dominio
│           └── ...
└── tests/
└── ...
```

---

## ⚙️ Configuración Modular y Validada

El sistema de configuración ha sido completamente rediseñado para mejorar la claridad, la validación y la sobreescritura flexible.

*   **Archivos Fragmentados:** La configuración monolítica `settings.json` ha sido dividida en archivos específicos por dominio en la carpeta `config/`:
    *   `llm_models.json`: Contiene todas las definiciones de modelos LLM, URLs de Ollama, timeouts y temperaturas.
    *   `agent_features.json`: Define las activaciones de características (feature flags) y configuraciones específicas para funcionalidades como el grafo de conocimiento, el contexto de decisión, etc.
    *   `tool_settings.json`: Configura el nivel de sandboxing, límites de tokens, ajustes de logging, rutas de prompts por defecto y otros parámetros operativos y de herramientas.
*   **Validación de Esquemas (Pydantic):** Cada fragmento de configuración es validado rigurosamente contra esquemas definidos con [Pydantic](https://pydantic-docs.helpmanual.io/). Esto asegura que la configuración cargada sea siempre correcta, previniendo errores en tiempo de ejecución debido a configuraciones mal formadas o incompletas.
*   **Carga Jerárquica y Sobreescritura:** El `ConfigLoader` en el `AgentKernel` es capaz de:
    1.  Cargar cada archivo de configuración.
    2.  Fusionar las configuraciones.
    3.  Permitir la sobreescritura de cualquier valor de configuración a través de variables de entorno (previamente definidas con el prefijo `OLLASH_`).

### **Ejemplo de Acceso a Configuración:**

Los agentes y servicios ahora acceden a la configuración de forma tipada y específica a través del `AgentKernel`:

```python
# Desde un agente o servicio que tiene acceso al kernel
llm_config = self.kernel.get_llm_models_config()
tool_config = self.kernel.get_tool_settings_config()

print(f"URL de Ollama: {llm_config.ollama_url}")
print(f"Modelo por defecto: {llm_config.default_model}")
print(f"Nivel de Sandbox: {tool_config.sandbox_level}")
print(f"Máximas iteraciones: {tool_config.max_iterations}")

# Sobreescritura vía variable de entorno:
# export OLLASH_LLM_MODELS_OLLAMA_URL="http://mi.ollama.server:8000"
# -> llm_config.ollama_url reflejaría el valor de la variable de entorno.
```

---

## 🛠️ Guía de Extensibilidad

El diseño modular de Ollash facilita enormemente su extensión y adaptación a nuevas necesidades.

### **Añadir una Nueva Herramienta:**

1.  **Define la Herramienta:** Crea una nueva clase en `src/utils/domains/<new_domain>/<new_tool_set.py>` que contenga tus métodos de herramienta.
2.  **Registra la Herramienta:** Utiliza el decorador `@register_tool` para hacer que la herramienta sea descubrible por el `ToolRegistry`.
3.  **Implementa la Lógica:** Tus métodos de herramienta tendrán acceso al `AgentKernel` y a los servicios proporcionados a través de él (logger, configuraciones, etc.).
4.  **Actualiza `tool_settings.json`:** Si tu herramienta requiere configuración específica o nuevos permisos, añádelos aquí y extienden el `ToolSettingsConfig` en `src/core/config_schemas.py` si es necesario.

### **Crear un Nuevo "Micro-Agent":**

1.  **Extiende `CoreAgent`:** Crea tu nuevo agente heredando de `src/agents/core_agent.py`.
2.  **Utiliza Mixins:** Aprovecha los mixins existentes (`IntentRoutingMixin`, `ToolLoopMixin`, `ContextSummarizerMixin`) para funcionalidades comunes y desarrolla nuevos mixins si es necesario.
3.  **Inyecta Dependencias:** Tu agente recibirá `AgentKernel`, `LLMClientManager` y otros servicios esenciales a través de inyección en su constructor, garantizando un bajo acoplamiento.
4.  **Define tu `run()` o `chat()`:** Implementa la lógica específica de tu micro-agente, orquestando las llamadas a LLMs y herramientas a través de las interfaces.

---

Este `README.md` es un reflejo de la robustez y el diseño reflexivo que subyacen en Ollash, preparándolo para un crecimiento continuo y una comunidad de desarrollo activa.
```