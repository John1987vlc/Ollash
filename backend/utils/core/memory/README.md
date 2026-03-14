# backend/utils/core/memory/

Sistemas de memoria del agente: episódica, errores, fragmentos de código, grafos de conocimiento y vector store.

## Archivos

| Archivo | Clase | Responsabilidad |
|---------|-------|----------------|
| `episodic_memory.py` | `EpisodicMemory` | Memoria cross-proyecto de soluciones a errores; SQLite + JSON |
| `error_knowledge_base.py` | `ErrorKnowledgeBase` | Patrones de errores aprendidos para prevención futura |
| `fragment_cache.py` | `FragmentCache` | Cache SQLite de fragmentos de código reutilizables (async) |
| `sqlite_vector_store.py` | `SQLiteVectorStore` | Vector store con cosine similarity; reemplaza ChromaDB |
| `chroma_manager.py` | `ChromaClientManager` | Shim de compatibilidad → devuelve `SQLiteVectorStore` |
| `automatic_learning.py` | `AutomaticLearning` | Aprende patrones de éxito/fallo automáticamente |
| `memory_manager.py` | `MemoryManager` | Facade que unifica acceso a todos los sistemas de memoria |
| `knowledge_graph_builder.py` | `KnowledgeGraphBuilder` | Construye grafos de conocimiento del proyecto |
| `decision_blackboard.py` | `DecisionBlackboard` | Registro de decisiones del agente para auditabilidad |
| `decision_context_manager.py` | `DecisionContextManager` | Gestiona contexto de decisiones multi-step |
| `cross_reference_analyzer.py` | `CrossReferenceAnalyzer` | Analiza referencias cruzadas entre memorias |
| `models.py` | Dataclasses | `EpisodicEntry`, `DecisionRecord`, `ErrorPattern`, `Fragment` |

## EpisodicMemory

SQLite en `{memory_dir}/episodic_index.db` + JSON por proyecto.

```python
memory = EpisodicMemory(memory_dir=".ollash/memory")

# Ciclo de sesión
session_id = memory.start_session(project_name="my_app")

# Registrar episodio
memory.record_episode(EpisodicEntry(
    project_name="my_app",
    phase_name="FileContentGeneration",
    error_type="syntax",
    solution_applied="Añadir import faltante",
    outcome="success"
))

# Consultar soluciones similares
solutions = memory.query_solutions(error_type="syntax", language="python")
similar = memory.query_similar_solutions(embedding_vector, threshold=0.8)

memory.end_session(session_id, summary="Proyecto completado con 2 errores")
```

## ErrorKnowledgeBase

```python
kb = ErrorKnowledgeBase(knowledge_dir=".ollash/knowledge")

# Registrar error
pattern_id = kb.record_error(
    error_msg="NameError: name 'foo' is not defined",
    file_path="src/main.py",
    context="En función process()"
)

# Consultar antes de generar código
warnings = kb.get_prevention_warnings(language="python", file_type=".py")
similar = kb.query_similar_errors(error_type="undefined", language="python")
```

## FragmentCache (async)

```python
cache = FragmentCache(db_path=".ollash/fragments.db")
await cache._init_db()   # Llamar explícitamente antes de usar

await cache.set("auth_jwt", code_fragment, fragment_type="function", language="python")
fragment = await cache.get("auth_jwt")
favorites = await cache.list_all(only_favorites=True)
similar = await cache.get_similar_examples("jwt authentication", language="python")
```

**IMPORTANTE**: `_init_db()` NO se llama en `__init__` — debe llamarse explícitamente.

## SQLiteVectorStore

Reemplaza ChromaDB. Zero dependencias externas extra.

```python
store = SQLiteVectorStore(db_path=".ollash/vectors.db")
collection = store.get_or_create_collection("code_embeddings")

collection.add(
    documents=["def authenticate(token): ..."],
    metadatas=[{"file": "auth.py"}],
    embeddings=[[0.1, 0.2, ...]],
    ids=["auth_fn_1"]
)

results = collection.query(
    query_embeddings=[[0.1, 0.2, ...]],
    n_results=5
)
```

Estrategia de búsqueda (en orden):
1. LIKE keyword search (rápido)
2. Cosine similarity sobre embeddings
3. Most-recent fallback
