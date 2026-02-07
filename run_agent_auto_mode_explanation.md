Claro, aquí tienes una explicación detallada del "modo auto", la gestión del tiempo y la seguridad del "sandbox" para `run_agent.py`:

---

### **1. Explicación del "Modo Auto" (`--auto`) en `run_agent.py`**

El argumento `--auto` en `run_agent.py` está diseñado para automatizar la interacción con el agente, eliminando la necesidad de confirmación manual para ciertas acciones. Esto es fundamental para escenarios de ejecución autónoma, como la "generación autónoma de proyectos", donde no hay un usuario interactivo que pueda aprobar cada paso.

**¿Qué hace?**
Cuando ejecutas `python run_agent.py "tu instrucción" --auto`, el agente interpretará la instrucción y procederá automáticamente con cualquier acción que normalmente requeriría tu confirmación explícita. Esto incluye:
*   **`write_file` (escribir en un archivo):** El agente escribirá el contenido en el archivo sin preguntar.
*   **`delete_file` (borrar un archivo):** El agente borrará el archivo sin preguntar.
*   **`git_commit` (hacer un commit en Git):** El agente realizará el commit de los cambios.
*   **`git_push` (hacer un push en Git):** El agente enviará los cambios al repositorio remoto.

**Uso:**
Simplemente añade `--auto` al comando de ejecución de tu agente:
```bash
docker-compose run --rm moltbot python run_agent.py "Genera un proyecto Flask simple para una lista de tareas" --auto
```

### **2. Cómo establecer un tiempo máximo de ejecución**

Puedes controlar el tiempo máximo de ejecución del agente de dos maneras principales:

*   **Límite de iteraciones del Agente (`max_iterations`):**
    *   **¿Qué es?** El agente tiene un límite de `max_iterations` (número máximo de "pasos" o "ciclos de pensamiento" que puede realizar) definido en el archivo `config/settings.json`. Por defecto, en las configuraciones actuales de prueba, puede ser 5 o 10, pero en un entorno de producción o para tareas complejas, suele ser un número mayor (ej. 30, 50).
    *   **Impacto:** Si el agente alcanza este número de iteraciones antes de completar su objetivo, se detendrá y reportará que ha excedido el límite de iteraciones. Este es el principal mecanismo para controlar el tiempo total que el agente dedicará a una tarea.
    *   **Cómo configurarlo:** Modifica el valor de `max_iterations` directamente en `config/settings.json`.
        ```json
        {
          "max_iterations": 30, // Cambia esto al valor deseado
          // ... otras configuraciones
        }
        ```
    *   **Nota:** `run_agent.py` actualmente no tiene un argumento CLI directo para `max_iterations`, por lo que la modificación debe hacerse en `settings.json`.

*   **Timeout por comando individual (`--timeout`):**
    *   **¿Qué es?** El argumento `--timeout` en `run_agent.py` establece un límite de tiempo (en segundos) para la ejecución de **cada comando individual** que el agente envía al sistema operativo (por ejemplo, `pip install`, `git clone`, etc.).
    *   **Impacto:** Si un comando específico (como una operación de red lenta o una compilación larga) excede este tiempo, se abortará, y el agente recibirá un error de "Timeout". Esto evita que comandos individuales se queden colgados indefinidamente.
    *   **Cómo configurarlo:** Pasa el argumento `--timeout` seguido del número de segundos al ejecutar `run_agent.py`.
        ```bash
        docker-compose run --rm moltbot python run_agent.py "Instrucción" --timeout 300
        ```

### **3. Cómo asegurar que el agente no se salga de la carpeta `sandbox`**

La seguridad del "sandbox" (es decir, asegurar que el agente opere exclusivamente dentro del directorio del proyecto designado y no acceda a áreas sensibles del sistema) se implementa mediante una combinación de mecanismos robustos:

1.  **Directorio de Trabajo Restringido (`CommandExecutor.working_dir`):**
    *   El agente, a través de su `CommandExecutor`, ejecuta todos los comandos de terminal (`run_command`) con su directorio de trabajo actual (`cwd`) configurado a la raíz del proyecto.
    *   **En Docker:** Cuando ejecutas con `docker-compose run --rm moltbot`, el volumen `.:/app` mapea la raíz de tu proyecto en el host al directorio `/app` dentro del contenedor. Así, `/app` se convierte en el `working_dir` del agente, y cualquier operación sin ruta absoluta se realizará dentro de él.

2.  **Detección de "Path Traversal" (`PolicyManager`):**
    *   El componente `PolicyManager` inspecciona activamente cada comando y sus argumentos antes de la ejecución.
    *   **Mecanismo:** Utiliza una expresión regular (`r"(\.\./|\.\.\)"`) para detectar patrones de "path traversal" (como `../` o `..`) que intentarían navegar a directorios fuera del `working_dir`. Si se detecta un patrón de este tipo, el comando **es bloqueado** por razones de seguridad.

3.  **Lista Blanca de Comandos (`PolicyManager.allowed_commands`):**
    *   En lugar de bloquear comandos peligrosos, el `PolicyManager` opera con una "lista blanca": solo los comandos explícitamente listados en `config/security_policies.json` (o los definidos por defecto si el archivo no existe) pueden ser ejecutados.
    *   **Impacto:** Esto previene la ejecución de comandos arbitrarios del sistema que podrían ser maliciosos o permitir al agente escapar de las restricciones del sandbox.

4.  **Nivel de Sandbox (`SandboxLevel.LIMITED`):**
    *   El `CommandExecutor` del agente se inicializa con `SandboxLevel.LIMITED`. Este nivel de sandbox, combinado con el `PolicyManager`, requiere que todas las operaciones de comando pasen las validaciones de las políticas de seguridad. Si el `PolicyManager` no está configurado o falla, se deniegan todos los comandos por seguridad.

5.  **Aislamiento de Docker:**
    *   Más allá de las salvaguardias del código del agente, Docker en sí proporciona un fuerte aislamiento. El agente opera dentro de su propio contenedor, que es un entorno separado del sistema operativo anfitrión.
    *   **Volúmenes:** Los volúmenes Docker (`moltbot_logs`, `moltbot_projects`) se utilizan para persistir los datos (logs, proyectos generados) de forma controlada, evitando que el agente pueda escribir arbitrariamente en cualquier parte del sistema de archivos de tu host.

**En resumen:**

La combinación del `CommandExecutor` (que restringe el `cwd`), el `PolicyManager` (que valida comandos y rutas), los `max_iterations` (para el tiempo de razonamiento) y el propio aislamiento de Docker, trabaja en conjunto para garantizar que el agente opere de forma segura y controlada dentro de su entorno designado, incluso en modo autónomo.

---

Let me know if you have any other questions!