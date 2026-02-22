# Guía para Contribuir a Local IT Agent - Ollash

¡Nos encanta recibir contribuciones! Si estás interesado en mejorar Local IT Agent - Ollash, aquí tienes una guía para empezar.

## ¿Cómo Contribuir?

Puedes contribuir de varias maneras:

1.  **Reportando Bugs:** Si encuentras un error, por favor, repórtalo.
2.  **Sugiriendo Características:** ¿Tienes una idea para una nueva funcionalidad o mejora? ¡Nos encantaría escucharla!
3.  **Enviando Código:** Si quieres escribir código para corregir un bug o implementar una característica.

## Reportando Bugs

Si encuentras un bug, por favor, abre un "Issue" en el repositorio de GitHub. Para que podamos ayudarte de manera efectiva, incluye la siguiente información:

*   **Descripción Clara:** Explica el bug de manera concisa.
*   **Pasos para Reproducir:** Describe los pasos exactos para reproducir el comportamiento inesperado.
*   **Comportamiento Esperado:** ¿Qué debería haber hecho el agente?
*   **Comportamiento Actual:** ¿Qué hizo el agente en su lugar?
*   **Entorno:** Versión de Python, versión de Ollama, modelo de LLM utilizado, sistema operativo.
*   **Logs:** Incluye cualquier mensaje de error o log relevante (`agent.log`).

## Sugiriendo Características

Para sugerir una característica, abre un "Issue" en el repositorio de GitHub. Describe tu idea con el mayor detalle posible, incluyendo:

*   **Problema:** ¿Qué problema resuelve esta característica?
*   **Solución Propuesta:** Describe la funcionalidad.
*   **Casos de Uso:** ¿Cómo se usaría esta característica?

## Enviando Pull Requests (PRs)

Si deseas contribuir con código, sigue estos pasos:

### 1. Configura tu Entorno de Desarrollo

1.  **Clona el Repositorio:**
    ```bash
    git clone https://github.com/John1987vlc/Ollash.git
    cd Ollash
    ```
2.  **Crea un Entorno Virtual:**
    ```bash
    python -m venv venv
    # En Windows:
    .\venv\Scripts\activate
    # En macOS/Linux:
    source venv/bin/activate
    ```
3.  **Instala las Dependencias:**
    ```bash
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    ```
4.  **Configura Ollama:**
    Asegúrate de tener [Ollama](https://ollama.ai/) instalado y en funcionamiento. Descarga el modelo `qwen3-coder:30b` (o el que uses para desarrollo):
    ```bash
    ollama pull qwen3-coder:30b
    ```

### 2. Crea una Nueva Rama

Crea una rama separada para tu característica o corrección de bug:

```bash
git checkout -b feature/nombre-de-tu-caracteristica-o-bugfix
```

### 3. Implementa tus Cambios

*   Escribe tu código.
*   Asegúrate de seguir los estándares de codificación del proyecto (PEP 8 para Python).
*   Añade tests unitarios para tus cambios. Si corriges un bug, añade un test que falle sin tu corrección y pase con ella. Si añades una característica, asegúrate de que esté bien cubierta por tests.

### 4. Ejecuta los Tests

Antes de enviar tu PR, asegúrate de que todos los tests pasen:

```bash
pytest
```

### 5. Documenta tus Cambios

Actualiza la documentación relevante (por ejemplo, `README.md` si tu cambio afecta la instalación o el uso, o docstrings en el código).

### 6. Envía tu Pull Request

1.  Haz un `commit` de tus cambios con un mensaje claro y descriptivo.
    ```bash
    git commit -m "feat: Describe tu característica o fix brevemente"
    ```
2.  Envía tu rama a GitHub:
    ```bash
    git push origin feature/nombre-de-tu-caracteristica-o-bugfix
    ```
3.  Abre un Pull Request en el repositorio de GitHub.
    *   Proporciona una descripción clara de los cambios.
    *   Referencia cualquier issue relacionado (ej. `Fixes #123`, `Closes #456`).
    *   Asegúrate de que la CI/CD pase correctamente.

## Pautas Adicionales

*   **Commits Atómicos:** Intenta que tus commits sean pequeños y se centren en un solo cambio lógico.
*   **Revisión de Código:** Tu PR será revisado por los mantenedores del proyecto. Sé receptivo a la retroalimentación.
*   **Código de Conducta:** Asegúrate de seguir nuestro `CODE_OF_CONDUCT.md` en todas tus interacciones.

¡Gracias por tu interés en contribuir!
