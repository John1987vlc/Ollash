"""Test runner: CRM básico en C# (.NET 8 Minimal API) via AutoAgent.

Usage:
    python run_crm_csharp_test.py

Output: generated_projects/auto_agent_projects/crm_basico_csharp/
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.core.containers import main_container

PROJECT_NAME = "crm_basico_csharp"
PROJECT_DESCRIPTION = """
CRM básico en C# (.NET 8) con Minimal API REST + consola de gestión.

FUNCIONALIDADES REQUERIDAS:
1. Gestión de Contactos:
   - Crear, leer, actualizar y eliminar contactos (CRUD completo)
   - Campos: Id, Nombre, Email, Teléfono, Empresa, FechaCreacion
   - Búsqueda por nombre o empresa (filtro simple)

2. Gestión de Leads (oportunidades):
   - CRUD de leads vinculados a un contacto
   - Campos: Id, ContactoId, Titulo, Valor (decimal), Estado (Nuevo/Seguimiento/Cerrado/Perdido), FechaCreacion
   - Filtrar leads por estado

3. Tareas/Actividades:
   - Crear tareas asociadas a un contacto o lead
   - Campos: Id, Titulo, Descripcion, FechaVencimiento, Completada (bool), ContactoId?
   - Marcar como completada

4. Persistencia:
   - SQLite mediante Entity Framework Core 8 (Microsoft.EntityFrameworkCore.Sqlite)
   - Un único DbContext: CrmDbContext
   - Migraciones NO requeridas; usar EnsureCreated() al iniciar

5. API REST (Minimal API, sin controladores):
   - GET/POST/PUT/DELETE /api/contactos
   - GET/POST/PUT/DELETE /api/leads
   - GET/POST/PUT/DELETE /api/tareas
   - Swagger/OpenAPI habilitado (Swashbuckle o built-in .NET 9 OpenAPI)

ESTRUCTURA DE ARCHIVOS ESPERADA:
- CrmBasico.csproj              → proyecto .NET 8, referencias a EF Core + SQLite
- Program.cs                    → entry point: builder, DI, rutas Minimal API, app.Run()
- Data/CrmDbContext.cs          → DbContext con DbSet<Contacto>, DbSet<Lead>, DbSet<Tarea>
- Models/Contacto.cs            → clase Contacto con propiedades y DataAnnotations básicas
- Models/Lead.cs                → clase Lead con enum EstadoLead
- Models/Tarea.cs               → clase Tarea
- Services/ContactoService.cs   → lógica CRUD para Contacto (interface + implementación)
- Services/LeadService.cs       → lógica CRUD para Lead
- Services/TareaService.cs      → lógica CRUD para Tarea
- README.md                     → instrucciones build/run y ejemplos curl
- .gitignore                    → .NET standard gitignore

RESTRICCIONES:
- Solo C# y paquetes NuGet estándar (.NET 8, EF Core 8, SQLite). Sin frameworks externos.
- Todas las clases con propiedades tipadas (no dynamic/object).
- Los servicios deben usar interfaces (IContactoService, ILeadService, ITareaService).
- Program.cs no superar 150 líneas; separar lógica en servicios.
- Sin autenticación (MVP local).
"""

NUM_REFINE_LOOPS = 1


def main() -> None:
    print("=" * 60)
    print(f"AutoAgent Test: {PROJECT_NAME}")
    print(f"Refine loops: {NUM_REFINE_LOOPS}")
    print("=" * 60)

    agent = main_container.auto_agent_module.auto_agent()

    start = time.monotonic()
    try:
        project_root = agent.run(
            description=PROJECT_DESCRIPTION,
            project_name=PROJECT_NAME,
            num_refine_loops=NUM_REFINE_LOOPS,
        )
        elapsed = time.monotonic() - start
        print(f"\n[OK] Project generated in {elapsed:.1f}s")
        print(f"     Path: {project_root}")
        _summarize(project_root)
    except Exception as exc:
        elapsed = time.monotonic() - start
        print(f"\n[ERROR] Pipeline failed after {elapsed:.1f}s: {exc}")
        raise


def _summarize(project_root: Path) -> None:
    """Print file tree + quality checks."""
    all_files = sorted(project_root.rglob("*"))
    code_files = [f for f in all_files if f.is_file() and not any(part.startswith(".") for part in f.parts)]
    print(f"\nGenerated {len(code_files)} files:")
    for f in code_files:
        size = f.stat().st_size
        rel = f.relative_to(project_root)
        print(f"  {rel}  ({size:,} bytes)")

    # Quality: stubs / empty files
    stubs: list[str] = []
    empty_files: list[str] = []
    for f in code_files:
        if f.suffix in {".cs", ".csproj", ".md"}:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                if len(text.strip()) < 20:
                    empty_files.append(str(f.relative_to(project_root)))
                elif "TODO" in text or "throw new NotImplementedException" in text:
                    stubs.append(str(f.relative_to(project_root)))
            except Exception:
                pass

    if empty_files:
        print(f"\n[WARN] Empty or near-empty files: {empty_files}")
    if stubs:
        print(f"\n[WARN] Files with stubs/TODOs: {stubs}")
    if not empty_files and not stubs:
        print("\n[OK] No obvious stubs or empty files detected")

    # Check expected files exist
    expected = [
        "Program.cs",
        "CrmBasico.csproj",
        "Data/CrmDbContext.cs",
        "Models/Contacto.cs",
        "Models/Lead.cs",
        "Models/Tarea.cs",
        "Services/ContactoService.cs",
        "Services/LeadService.cs",
        "Services/TareaService.cs",
        "README.md",
    ]
    missing = [e for e in expected if not (project_root / e).exists()]
    if missing:
        print(f"\n[WARN] Expected files missing: {missing}")
    else:
        print("\n[OK] All expected files present")

    # C#-specific checks
    _check_csharp_quality(project_root, code_files)


def _check_csharp_quality(project_root: Path, code_files: list[Path]) -> None:
    """Heuristic quality checks for C# code."""
    issues: list[str] = []

    for f in code_files:
        if f.suffix != ".cs":
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            rel = str(f.relative_to(project_root))
            # Services should use interfaces
            if "Service.cs" in rel and "interface I" not in text and ": I" not in text:
                issues.append(f"{rel}: missing interface definition or implementation")
            # DbContext check
            if "CrmDbContext.cs" in rel and "DbSet<" not in text:
                issues.append(f"{rel}: DbContext has no DbSet<> properties")
            # Program.cs should register DI
            if "Program.cs" in rel and "builder.Services.Add" not in text:
                issues.append(f"{rel}: no DI registration (builder.Services.Add...)")
        except Exception:
            pass

    if issues:
        print("\n[WARN] C# quality issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n[OK] C# quality checks passed")


if __name__ == "__main__":
    main()
