# 🏢 Ollash Knowledge Workspace - Guía de Implementación

## 📚 Introducción

El **Knowledge Workspace** es un sistema empresarial de gestión de documentos y análisis integrado en Ollash, inspirado en **Anthropic Cowork**. Permite a los usuarios:

1. **Subir documentos** (PDF, DOCX, TXT, Markdown) como contexto persistente
2. **Indexación automática** mediante monitoreo de carpetas
3. **Análisis inteligente** con roles especializados (analyst, writer)
4. **Síntesis en cascada** para documentos muy largos
5. **Generación de tareas** basadas en requisitos
6. **Análisis proactivo de logs** para detectar riesgos

---

## 📁 Estructura de Carpetas

```
knowledge_workspace/
├── references/           # Documentos subidos por el usuario
│   ├── requisitos.pdf
│   ├── especificaciones.docx
│   └── ...
├── indexed_cache/        # Índices ChromaDB (gestionados internamente)
└── summaries/            # Resúmenes generados
    ├── documento_executive.md
    └── ...
```

---

## 🚀 Uso Rápido

### 1. Subir un Documento

```python
from pathlib import Path
from src.utils.core.documentation_manager import DocumentationManager

doc_manager = DocumentationManager(Path("."), logger)

# Copiar archivo a knowledge_workspace/references/
success = doc_manager.upload_to_workspace(Path("mi_documento.pdf"))
```

### 2. Monitoreo Automático (IndexadorWatcher)

```python
from src.utils.core.documentation_watcher import DocumentationWatcher

watcher = DocumentationWatcher(
    references_dir=knowledge_workspace / "references",
    documentation_manager=doc_manager,
    logger=logger,
    check_interval=5  # segundos
)

watcher.start()  # Indexación automática al añadir archivos
# ... tu aplicación ...
watcher.stop()
```

### 3. Buscar en el Workspace

```python
# Búsqueda semántica
results = doc_manager.query_documentation(
    query="¿Cuáles son los requisitos de seguridad?",
    n_results=5
)

for result in results:
    print(f"Fuente: {result['source']}")
    print(f"Relevancia: {result['distance']}")
    print(f"Contenido: {result['document'][:200]}...")
```

### 4. Generar Resumen Ejecutivo

```python
from src.utils.core.cascade_summarizer import CascadeSummarizer

summarizer = CascadeSummarizer(ollama_client, logger)

result = summarizer.cascade_summarize(
    text=document_content,
    title="Especificación de Sistema"
)

print(result["executive_summary"])
summarizer.save_summary(result, Path("knowledge_workspace/summaries"))
```

---

## 🎭 Nuevos Roles LLM

### Rol: `analyst`

Optimizado para **síntesis y análisis crítico**.

**Capacidades:**
- Extracción de points clave
- Análisis de riesgos
- Identificación de brechas
- Comparativa de opciones

**Uso:**
```python
agent.call_llm_role(
    role="analyst",
    prompt="Analiza estos requisitos y extrae los 5 puntos más críticos",
    context=document_text
)
```

**Plantillas disponibles:**
- `executive_summary`: Resumen ejecutivo
- `key_insights`: Puntos clave
- `risk_analysis`: Análisis de riesgos
- `gap_analysis`: Brechas en información
- `comparative_analysis`: Comparativa

### Rol: `writer`

Optimizado para **composición narrativa y formateo**.

**Capacidades:**
- Adaptación de tono (ejecutivo, técnico, general)
- Reformateo de documentos
- Corrección gramatical
- Reestructuración de contenido

**Uso:**
```python
agent.call_llm_role(
    role="writer",
    prompt="Reescribe esto en tono ejecutivo para directivos",
    context=technical_document
)
```

**Plantillas disponibles:**
- `tone_adjustment`: Cambiar tono/audiencia
- `executive_brief`: Crear un brief ejecutivo
- `technical_documentation`: Documentación técnica formal
- `grammar_edit`: Corrección y pulido
- `content_restructure`: Reorganización lógica
- `audience_adaptation`: Múltiples versiones para diferentes audiencias

---

## 🔧 Herramientas de Cowork Integradas

### 1. `document_to_task`

Convierte requisitos en tareas automáticamente.

```python
from src.utils.domains.bonus.cowork_impl import CoworkTools

cowork = CoworkTools(doc_manager, ollama, logger, knowledge_workspace)

result = cowork.document_to_task(
    document_name="requisitos.pdf",
    task_category="automation",  # o: integration, deployment, etc.
    priority="high",
    output_format="json"  # Genera tareas en tasks.json
)

print(f"Tareas generadas: {result['tasks_generated']}")
```

**Output:** Tareas JSON con estructura:
```json
{
  "task_id": "req-001",
  "name": "Implementar autenticación OAuth2",
  "description": "...",
  "dependencies": [],
  "estimated_effort": 8,
  "acceptance_criteria": [...]
}
```

### 2. `analyze_recent_logs`

Análisis proactivo de logs buscando riesgos.

```python
result = cowork.analyze_recent_logs(
    log_type="security",      # system, application, security, network, database
    time_period="24hours",    # 1hour, 6hours, 24hours, 7days
    risk_threshold="high",    # critical, high, medium, low, all
    top_n=5                   # Top N riesgos a reportar
)

# Resultado: Análisis de riesgos prioritizados
```

### 3. `generate_executive_summary`

Resumen ejecutivo con síntesis en cascada.

```python
result = cowork.generate_executive_summary(
    document_name="especificaciones.docx",
    summary_type="executive",  # o: technical, general, key_insights
    max_length=250,
    include_recommendations=True
)

# Guarda resumen en knowledge_workspace/summaries/
print(result["summary"])
```

### 4. `query_knowledge_workspace`

Búsqueda semántica en todo el workspace.

```python
results = doc_manager.query_documentation_by_source(
    query="¿Cuáles son los requisitos de backup?",
    source_filter=".pdf"  # Opcional: filtrar por formato
)
```

---

## 🏗️ Arquitectura Técnica

### Flujo de Indexación

```
Archivo nuevo en references/
    ↓
DocumentationWatcher detecta cambio
    ↓
MultiFormatIngester extrae texto (PDF, DOCX, etc.)
    ↓
DocumentationManager chunka + genera embeddings
    ↓
ChromaDB almacena vectores
    ↓
query_documentation() busca semánticamente
```

### Flujo de Síntesis en Cascada

```
Documento largo (> 2000 palabras)
    ↓
CascadeSummarizer.chunk_text() → fragmentos
    ↓
Map phase: Resumir cada fragmento
    ↓
Reduce phase: Sintetizar resúmenes en resumen final
    ↓
Output: Compresión de contenido sin halucinar
```

---

## 📊 Integración con UI

### Cambios Esperados (Frontend)

1. **Panel de Workspace** (nueva sección sidebar):
   - Listar documentos en `references/`
   - Botón "Subir documento"
   - Estado de indexación

2. **Artifact Panel Mejorado**:
   - Renderizado de Markdown (marked.js)
   - Vista previa de resúmenes
   - Botones de refactorización:
     - "Acortar"
     - "Cambiar tono a profesional"
     - "Expandir con detalles"

3. **Nuevas herramientas visibles en chat**:
   - document_to_task
   - analyze_recent_logs
   - generate_executive_summary
   - query_knowledge_workspace

---

## 📦 Dependencias Opcionales

Para soporte completo de formatos:

```bash
pip install PyPDF2 python-docx python-pptx
```

Sin estos, el sistema funciona parcialmente (solo TXT, MD).

---

## 🧪 Ejemplos de Uso Completo

### Ejemplo 1: Documento a Plan de Automatización

```python
# Usuario sube "plan_seguridad.pdf"
# Watcher detecta automáticamente

# Agent recibe comando:
# "Crea tareas del plan_seguridad.pdf"

agent.call_tool("document_to_task", {
    "document_name": "plan_seguridad.pdf",
    "task_category": "security",
    "priority": "critical"
})

# Resultado: N nuevas tareas en tasks.json
```

### Ejemplo 2: Análisis Proactivo Diario

```python
# Daily cron job
cowork = CoworkTools(...)

result = cowork.analyze_recent_logs(
    log_type="all",
    time_period="24hours",
    risk_threshold="high"
)

# Genera resumen de top 5 riesgos → envía email a seguridad
```

### Ejemplo 3: Síntesis de Especificaciones

```python
# Usuario: "Hazme un resumen ejecutivo de especificaciones.docx"

result = cowork.generate_executive_summary(
    document_name="especificaciones.docx",
    summary_type="executive",
    include_recommendations=True
)

# UI renderiza el Markdown con marked.js
# Usuario ve: Resumen conciso + acciones recomendadas
```

---

## 🔒 Seguridad

- Documentos en `knowledge_workspace/` permanecen en el sistema local
- Índices ChromaDB no están públicos
- Queries usan embeddings (sin enviar texto completo al LLM)
- Los resúmenes se almacenan en `summaries/` sin compartir

---

## 🚨 Limitaciones Conocidas

1. **Token limits**: Documents > 10K palabras necesitan `cascade_summarizer`
2. **Formatos binarios**: Requiere PyPDF2, python-docx instalado
3. **Logs grandes**: `analyze_recent_logs` limita a últimas 500 líneas por archivo
4. **Búsqueda**: ChromaDB indexa, pero grandes corpus necesitan filtros

---

## 📝 Next Steps (UI + Integración)

- [ ] Panel de "Knowledge Workspace" en sidebar
- [ ] Upload form con preview de documento
- [ ] Visualización de índice en tiempo real
- [ ] Integración de `marked.js` para Markdown rendering
- [ ] Botones de refactorización en artifact panel
- [ ] Hooks de herramientas Cowork en chat interface

---

**Para más detalles técnicos**, consulta los archivos:
- `src/utils/core/documentation_manager.py` - Gestión central
- `src/utils/core/cascade_summarizer.py` - Síntesis
- `src/agents/prompt_templates.py` - Plantillas de roles
- `src/utils/domains/bonus/cowork_impl.py` - Implementación de herramientas

