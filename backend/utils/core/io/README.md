# backend/utils/core/io/

Operaciones de entrada/salida: gestión de archivos, checkpoints, git, artefactos e ingesta de documentos.

## Archivos

| Archivo | Clase | Responsabilidad |
|---------|-------|----------------|
| `file_manager.py` | `FileManager` | CRUD de archivos del proyecto; `write_file_async()`, `read_file_async()`, `delete_file_async()` |
| `checkpoint_manager.py` | `CheckpointManager` | Guarda/restaura snapshots del estado de proyecto en JSON; operaciones async via `asyncio.to_thread()` |
| `git_manager.py` | `GitManager` | `git status`, `git diff`, `git commit`, `git log`, `git clone` |
| `artifact_manager.py` | `ArtifactManager` | Almacena y recupera artefactos generados (binarios, docs, reports) |
| `documentation_manager.py` | `DocumentationManager` | Gestiona docs generadas; sincroniza con el proyecto |
| `export_manager.py` | `ExportManager` | Exporta proyectos en ZIP, TAR o formato personalizado |
| `locked_file_manager.py` | `LockedFileManager` | FileManager con locks para acceso concurrente seguro |
| `models.py` | Dataclasses | `FileInfo`, `CheckpointEntry`, `ArtifactRecord` |
| `multi_format_ingester.py` | `MultiFormatIngester` | Convierte PDF, DOCX, PPTX, TXT, MD a texto plano |
| `project_ingestion_service.py` | `ProjectIngestionService` | Ingesta un proyecto existente; devuelve `(files, structure, paths, readme_content)` |

## FileManager

```python
fm = FileManager(project_root)

# Sync
fm.write_file("src/main.py", content)
content = fm.read_file("src/main.py")
fm.delete_file("src/old.py")

# Async (no bloquea el event loop)
await fm.write_file_async("src/main.py", content)
content = await fm.read_file_async("src/main.py")
```

## CheckpointManager

```python
cm = CheckpointManager(project_root)
await cm.save_dag(dag_state, checkpoint_name="phase_5")
dag_state = await cm.load_dag(checkpoint_name="phase_5")
await cm.cleanup_old(keep_last=5)
```

## MultiFormatIngester

Formatos soportados: `.pdf`, `.docx`, `.pptx`, `.txt`, `.md`, `.markdown`

```python
ingester = MultiFormatIngester()
text = ingester.ingest_file("document.pdf")      # → str
results = ingester.ingest_directory("./docs/")   # → Dict[str, str]
meta = ingester.get_file_metadata("document.pdf") # → FileMetadata
```

Dependencias opcionales (lazy-loaded): `PyPDF2`, `python-docx`, `python-pptx`. Si no están instaladas, el formato correspondiente devuelve string vacío con warning.

## ProjectIngestionService

```python
svc = ProjectIngestionService()
files, structure, paths, readme = svc.ingest("/path/to/project")
# files     → Dict[str, str] ruta → contenido
# structure → Dict árbol de directorios
# paths     → List[str] todos los paths
# readme    → str contenido del README.md (o "" si no existe)
```
