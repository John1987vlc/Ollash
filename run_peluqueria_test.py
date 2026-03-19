"""Test runner: peluquería booking web app via AutoAgent with 2 refine loops.

Usage:
    python run_peluqueria_test.py

Output: generated_projects/auto_agent_projects/peluqueria_reservas/
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.core.containers import main_container

PROJECT_NAME = "peluqueria_reservas"
PROJECT_DESCRIPTION = """
Web app de reservas para una peluquería con panel de administración.

FUNCIONALIDADES REQUERIDAS:
1. Página pública de reservas:
   - Formulario para que el cliente seleccione servicio (corte, tinte, manicura, etc.)
   - Selector de fecha y hora según disponibilidad real
   - Campo de nombre y teléfono del cliente
   - Confirmación visual tras reservar

2. Panel de administración (/admin):
   - Login con usuario/contraseña (admin/admin1234)
   - Gestión de disponibilidad: el admin puede marcar horas disponibles o no por día
   - Vista de todas las reservas del día/semana
   - Posibilidad de cancelar/confirmar reservas

STACK: Python (FastAPI o Flask), HTML/CSS/JS vanilla, SQLite para datos.
Sin frameworks frontend pesados. Toda la lógica en el servidor.
Incluir al menos: app.py (servidor), index.html (reservas), admin.html (panel),
static/style.css, static/app.js, requirements.txt.
"""

NUM_REFINE_LOOPS = 2


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
    """Print a quick file tree + size overview."""
    all_files = sorted(project_root.rglob("*"))
    code_files = [f for f in all_files if f.is_file() and not any(part.startswith(".") for part in f.parts)]
    print(f"\nGenerated {len(code_files)} files:")
    for f in code_files:
        size = f.stat().st_size
        rel = f.relative_to(project_root)
        print(f"  {rel}  ({size:,} bytes)")

    # Quick quality check: look for obvious stubs
    stubs = []
    for f in code_files:
        if f.suffix in {".py", ".js", ".html"}:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                if "TODO" in text or "pass\n" in text or "NotImplementedError" in text:
                    stubs.append(str(f.relative_to(project_root)))
            except Exception:
                pass
    if stubs:
        print(f"\n[WARN] Files with stubs/TODOs: {stubs}")
    else:
        print("\n[OK] No obvious stubs detected")


if __name__ == "__main__":
    main()
