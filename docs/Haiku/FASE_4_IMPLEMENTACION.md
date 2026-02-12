# 🔄 Fase 4: Sistema de Ciclos de Crítica y Validación

**Estado**: ✅ COMPLETADA Y PROBADA (26/26 tests pasando)

---

## 📋 Descripción General

Fase 4 implementa un **sistema completo de refinamiento de texto** basado en ciclos iterativos de:
1. **Crítica automática** (claridad, concisión, estructura, precisión)
2. **Refinamiento** (aplicación de mejoras)
3. **Validación contra fuentes** (verificación de precisión)
4. **Orquestación de workflows** (coordinación de múltiples ciclos)

---

## 🏗️ Arquitectura

### 4 Componentes Core + 1 Blueprint

```
src/utils/core/
├── feedback_refinement_manager.py    (Gestión de párrafos y críticas)
├── source_validator.py               (Validación contra fuentes originales)
├── refinement_orchestrator.py         (Orquestación de workflows)
└── [3 nuevos managers]

src/web/blueprints/
└── refinement_bp.py                  (14 API endpoints)
```

---

## 📊 Componentes Implementados

### 1. FeedbackRefinementManager (400 líneas)
Gestiona párrafos individuales y genera críticas.

**Funcionalidades**:
- Extrae párrafos de documentos
- Calcula score de legibilidad automático (0-100)
- Genera 4 tipos de crítica:
  - `clarity` - Detecta oraciones largas, voz pasiva, palabras complejas
  - `conciseness` - Identifica palabras repetidas, rellenos ("very", "really")
  - `structure` - Valida número de oraciones, estructura de tema
  - `accuracy` - Requiere comparación con fuentes

**Clases Clave**:
```python
@dataclass
class ParagraphContext:
    index: int
    text: str
    original_text: str
    source_id: str
    readability_score: float
    refinement_history: List[RefinementRecord]

@dataclass
class RefinementRecord:
    timestamp: str
    action_type: str      # 'critique', 'refine', 'validate', 'rollback'
    original: str
    refined: str
    feedback_score: float
    applied: bool
```

**Métodos Principales**:
```python
extract_paragraphs(text, source_id) → List[ParagraphContext]
select_paragraphs_for_refinement(paragraphs, criteria) → List[ParagraphContext]
generate_critique(paragraph, critique_type) → str
apply_refinement(paragraph, refinement_text, critique) → RefinementRecord
get_refinement_summary() → Dict
```

---

### 2. SourceValidator (450 líneas)
Valida refinamientos contra documentos fuente originales.

**Funcionalidades**:
- Registra documentos fuente para referencia
- Valida preservación semántica (word overlap)
- Detecta contradicciones (cambios de negación)
- Verifica consistencia de hechos
- Compara versiones original vs refinada

**Tipos de Validación**:
- `semantic` - ¿Se preserva el significado?
- `factual` - ¿Se mantienen los hechos?
- `full` - Ambas validaciones

**Métricas de Validación**:
```python
@dataclass
class ValidationResult:
    is_valid: bool                    # True si score >= 70%
    validation_score: float           # 0-100
    issues: List[ValidationIssue]
    confidence_level: str             # high, medium, low
```

**Métodos**:
```python
register_source(source_id, source_text) → bool
validate_refinement(original, refined, source_id, type) → ValidationResult
compare_versions(original, refined) → Dict
suggest_rollback(result) → bool
get_validation_report() → Dict
```

---

### 3. RefinementOrchestrator (600 líneas)
Orquesta workflows complejos de refinamiento multi-párrafo.

**Características**:
- 4 estrategias predefinidas
- Gestión de workflows con persistencia
- Análisis de documentos
- Ejecución de refinamientos iterativos
- Exportación en múltiples formatos

**Estrategias Disponibles**:

| Estrategia | Critique Types | Validation | Auto-Apply | Iteraciones |
|-----------|---|---|---|---|
| `quick_polish` | clarity | 80% | ✅ | 1 |
| `comprehensive` | clarity, conciseness, structure | 75% | ❌ | 3 |
| `accuracy_focused` | accuracy | 85% | ❌ | 2 |
| `aggressive_rewrite` | all | 70% | ❌ | 5 |

**Workflow Lifecycle**:
```
created → analyzing → refining → validating → completed
```

**Persistencia**:
```
knowledge_workspace/workflows/
├── wf_id1.json          # estado del workflow
├── wf_id2.json
└── ...
```

---

### 4. RefinementBlueprint (14 Endpoints)
API REST para acceso a todas las funcionalidades.

**Endpoints Disponibles**:

#### Workflow Management (6 endpoints)
```
POST   /api/refinement/workflow/create         Crear workflow nuevo
GET    /api/refinement/workflow/<id>/analyze   Analizar documento
POST   /api/refinement/workflow/<id>/refine    Ejecutar refinamiento
GET    /api/refinement/workflow/<id>/status    Obtener estado
GET    /api/refinement/workflow/list           Listar workflows
GET    /api/refinement/workflow/<id>/export    Exportar documento
```

#### Paragraph Refinement (2 endpoints)
```
POST   /api/refinement/paragraph/critique      Generar crítica
POST   /api/refinement/paragraph/compare       Comparar versiones
```

#### Validation (2 endpoints)
```
POST   /api/refinement/validate                Validar refinamiento
GET    /api/refinement/validation/report       Reporte de validación
```

#### Source Management (2 endpoints)
```
POST   /api/refinement/source/register         Registrar fuente
GET    /api/refinement/source/<id>             Obtener fuente
```

#### Metrics & Config (2 endpoints)
```
GET    /api/refinement/metrics/summary         Métricas generales
GET    /api/refinement/strategies              Listar estrategias
```

---

## 📡 Ejemplos de API

### Crear Workflow de Refinamiento
```bash
curl -X POST http://localhost:5000/api/refinement/workflow/create \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "doc_refinement_001",
    "source_id": "original_doc",
    "document_text": "Full document text here with multiple paragraphs...",
    "strategy": "comprehensive"
  }'

# Response:
{
  "status": "success",
  "workflow": {
    "workflow_id": "doc_refinement_001",
    "status": "created",
    "total_paragraphs": 5,
    "created_at": "2026-02-11T10:30:00",
    "paragraphs": [...]
  }
}
```

### Analizar Documento
```bash
curl http://localhost:5000/api/refinement/workflow/doc_refinement_001/analyze

# Response:
{
  "status": "success",
  "analysis": {
    "total_paragraphs": 5,
    "average_readability": 62.4,
    "paragraphs_needing_improvement": [
      {
        "index": 2,
        "readability": 35.2,
        "word_count": 156
      }
    ]
  }
}
```

### Ejecutar Refinamiento
```bash
curl -X POST http://localhost:5000/api/refinement/workflow/doc_refinement_001/refine \
  -H "Content-Type: application/json" \
  -d '{
    "strategy": "comprehensive",
    "paragraph_indices": [2, 3]
  }'

# Response:
{
  "status": "success",
  "results": {
    "refinements": [...],
    "validations": [
      {
        "paragraph_index": 2,
        "is_valid": true,
        "score": 82.5,
        "issues": 1
      }
    ]
  }
}
```

### Validar Párrafo
```bash
curl -X POST http://localhost:5000/api/refinement/validate \
  -H "Content-Type: application/json" \
  -d '{
    "original_text": "The system uses cloud infrastructure.",
    "refined_text": "The system uses reliable cloud infrastructure.",
    "source_id": "original_doc",
    "validation_type": "full"
  }'

# Response:
{
  "status": "success",
  "is_valid": true,
  "validation_score": 88.0,
  "confidence": "high",
  "issue_count": 0,
  "issues": []
}
```

---

## 🧪 Cobertura de Tests

**26 tests completados - 100% passing**:

### TestFeedbackRefinementManager (8 tests)
- ✅ Extracción de párrafos
- ✅ Cálculo de legibilidad
- ✅ Selección por criterios
- ✅ Crítica de claridad
- ✅ Crítica de concisión
- ✅ Crítica de estructura
- ✅ Aplicación de refinamientos
- ✅ Resumen de métricas

### TestSourceValidator (7 tests)
- ✅ Registro de fuentes
- ✅ Obtención de fuentes
- ✅ Validación completa
- ✅ Detección de drift semántico
- ✅ Comparación de versiones
- ✅ Sugerencia de rollback
- ✅ Reporte de validación

### TestRefinementOrchestrator (9 tests)
- ✅ Creación de workflows
- ✅ Listado de estrategias
- ✅ Análisis de documentos
- ✅ Ejecución de refinamientos
- ✅ Obtención de estado
- ✅ Listado de workflows
- ✅ Exportación a texto
- ✅ Exportación a HTML
- ✅ Exportación a Markdown

### TestRefinementIntegration (2 tests)
- ✅ Workflow completo end-to-end
- ✅ Validación integrada

---

## 💾 Almacenamiento de Datos

### Estructura de Directorios
```
knowledge_workspace/
├── refinements/
│   ├── refinement_metrics.json      # Métricas agregadas
│   ├── refinement_history.json      # Historial de acciones
│   └── [batch data files]
├── validations/
│   ├── validation_log.json          # Log de validaciones
│   └── [validation records]
├── sources/
│   ├── source_id1.txt               # Documentos fuente
│   ├── source_id2.txt
│   └── ...
└── workflows/
    ├── workflow_id1.json            # Estados de workflows
    ├── workflow_id2.json
    └── ...
```

### Formato de Almacenamiento
Todos los datos se persisten en JSON para máxima portabilidad y debugging.

**Ejemplo: Métricas de Refinamiento**
```json
{
  "total_paragraphs": 15,
  "refined_count": 8,
  "validation_passed": 7,
  "validation_failed": 1,
  "avg_readability_improvement": 12.3,
  "total_iterations": 24
}
```

---

## 🔄 Flujos de Uso

### Flujo 1: Refinamiento Rápido
```
Usuario sube documento
↓
Sistema extrae párrafos
↓
Ejecuta quick_polish (solo clarity)
↓
Auto-aplica cambios
↓
Retorna documento refinado
```

### Flujo 2: Refinamiento Comprobado
```
Usuario crea workflow con datos fuente
↓
Sistema analiza problemas de legibilidad
↓
Usuario selecciona párrafos problemáticos
↓
Sistema genera críticas (clarity, conciseness, structure)
↓
Usuario revisa y aprueba refinamientos
↓
Sistema valida contra fuentes originales
↓
Si validation_score >= 75%: aplica cambios
↓
Retorna documento con histórico de cambios
```

### Flujo 3: Investigación de Problemas
```
Usuario registra fuente original
↓
Usuario sube versión cuestionable
↓
Sistema detecta contradictions/drift semántico
↓
Sistema reporta issues específicas
↓
Sugiere rollback o correcciones
```

---

## 🚀 Características Avanzadas

### 1. Validación Semántica
Usa word overlap para detectar cambios de significado:
```python
similarity = len(words_original & words_refined) / len(words_original)
# Si < 0.3 → semantic drift crítico
# Si 0.3-0.5 → warning
```

### 2. Detección de Contradicciones
Busca cambios en negaciones:
```python
"It is NOT important" → "It IS important"  # Detectado como CRITICAL
```

### 3. Preservación de Hechos
Extrae hechos clave (entrecomillado, números) y verifica que se mantengan.

### 4. Múltiples Formatos de Exportación
```python
export_workflow_document(id, "text")      # Texto plano
export_workflow_document(id, "markdown")  # Markdown con metadata
export_workflow_document(id, "html")      # HTML renderizable
```

---

## 📈 Métricas Disponibles

Por workflow:
```json
{
  "total_paragraphs": 10,
  "refined": 6,
  "completion_time": "2026-02-11T10:45:00",
  "passed_validation": 5,
  "validation_rate": 83.3
}
```

Globales:
```json
{
  "total_refinements": 125,
  "avg_readability_improvement": 8.7,
  "validation_pass_rate": 81.2,
  "avg_validation_score": 79.5
}
```

---

## 🔧 Integración con Flask

App.py incluye:
```python
# Importación
from src.web.blueprints.refinement_bp import refinement_bp, init_refinement

# Inicialización
init_refinement(app)

# Registro
app.register_blueprint(refinement_bp)
```

Los managers se crean durante `init_refinement()`:
```python
refinement_manager = FeedbackRefinementManager(workspace)
validator = SourceValidator(workspace)
orchestrator = RefinementOrchestrator(workspace)
```

---

## ⚙️ Configuración

En `config/settings.json`:
```json
{
  "features": {
    "feedback_cycles": true,        // FASE 4
    "refinement_validation": true,
    "semantic_checking": true
  },
  "refinement": {
    "min_validation_score": 70,
    "max_iterations": 5,
    "readability_target": 75.0
  }
}
```

Para desactivar:
```json
"feedback_cycles": false
```

---

## 🐛 Manejo de Errores

### Validación Falle
- ✅ Sugiere correcciones específicas
- ✅ Permite rollback
- ✅ Loguea issues para auditoría

### Fuente No Encontrada
- ⚠️ Validation corre con confianza = "low"
- ⚠️ Se sugiere registrar fuente
- ✅ No bloquea el proceso

### Drift Semántico Detectado
- 🚩 CRITICAL si similarity < 0.3
- ⚠️ WARNING si 0.3-0.5
- 📝 Propone relectura/revisión

---

## 📚 Próximos Pasos (Fase 5)

Fase 5 añadirá:
- **OCR** (deepseek-ocr:3b) - Extraer texto de imágenes
- **Web Speech API** - Transcripción de audio
- **Multimodal Ingestion** - Combinar múltiples formatos

---

## ✅ Checklist de Validación

- ✅ 3 managers creados (400+450+600 líneas)
- ✅ 1 Blueprint con 14 endpoints
- ✅ 26 tests completados - 100% passing
- ✅ Integración con app.py
- ✅ Persistencia en JSON
- ✅ Documentación completa
- ✅ Ejemplos de API funcionando
- ✅ Manejo de errores implementado
- ✅ Validación semántica activa
- ✅ Exportación multi-formato

---

## 🎯 Próximos Pasos Inmediatos

### Para Desarrolladores
1. Revisar `tests/unit/test_phase4_refinement.py` para ejemplos
2. Probar endpoints via Postman o curl
3. Integrar con UI frontend (opcional)

### Para Usuarios
1. Registrar documentos fuente
2. Crear workflows con `POST /api/refinement/workflow/create`
3. Analizar con `/analyze`
4. Refinar con `/refine`
5. Descargar resultados con `/export`

### Para Deployment
1. Verificar `knowledge_workspace/` tiene permisos de escritura
2. Configurar storage si se usa en cloud
3. Monitorear métrica `validation_pass_rate`

---

**Fase 4 COMPLETADA ✅**

*Todas las validaciones pasadas, documentación completa, código production-ready*
