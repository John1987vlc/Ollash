"""Test runner: PyVault – local encrypted password manager via AutoAgent.

Usage:
    python run_pyvault_test.py

Output: generated_projects/auto_agent_projects/pyvault/
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.core.containers import main_container

PROJECT_NAME = "pyvault"
PROJECT_DESCRIPTION = """
PyVault – gestor de contraseñas local en Python para la terminal.

FUNCIONALIDADES REQUERIDAS:
1. Almacenamiento cifrado:
   - Base de datos SQLite local (~/.pyvault/vault.db)
   - Cifrado AES-256-GCM de todas las contraseñas usando cryptography (Fernet)
   - Clave maestra derivada con PBKDF2-HMAC-SHA256 (salt almacenado en vault.db)
   - El vault se bloquea automáticamente tras 5 minutos de inactividad

2. CLI completa (usando argparse o click):
   - pyvault init            → crea el vault con nueva clave maestra
   - pyvault add <name>      → agrega entrada (url, usuario, contraseña generada o manual)
   - pyvault get <name>      → muestra entrada (copia al portapapeles si pyperclip disponible)
   - pyvault list            → lista todas las entradas (nombre + url, SIN mostrar contraseñas)
   - pyvault delete <name>   → elimina entrada con confirmación
   - pyvault generate        → genera contraseña aleatoria segura (longitud configurable)
   - pyvault export          → exporta a CSV cifrado
   - pyvault import          → importa desde CSV (formato compatible con Bitwarden)

3. Arquitectura modular:
   - vault/crypto.py         → funciones de cifrado/descifrado y derivación de clave
   - vault/storage.py        → capa de acceso a SQLite (VaultStorage class)
   - vault/cli.py            → interfaz de línea de comandos
   - vault/models.py         → dataclasses: VaultEntry, VaultConfig
   - vault/generator.py      → generador de contraseñas seguras con opciones
   - main.py                 → entry point (ejecuta cli)
   - requirements.txt        → cryptography, click (o argparse), pyperclip (opcional)
   - README.md               → instrucciones de instalación y uso
   - tests/test_crypto.py    → tests unitarios del módulo crypto
   - tests/test_storage.py   → tests unitarios del módulo storage
   - tests/test_generator.py → tests unitarios del generador

RESTRICCIONES:
- Solo Python stdlib + cryptography + click. Sin dependencias pesadas.
- No almacenar nunca la clave maestra en texto plano ni en memoria más de lo necesario.
- Todo el código tipado con type hints. Docstrings en funciones públicas.
- Los tests deben poder ejecutarse con pytest sin configuración adicional.
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

    # Quality check: stubs / incomplete code
    stubs = []
    empty_files = []
    for f in code_files:
        if f.suffix in {".py", ".js", ".html", ".md"}:
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                if len(text.strip()) < 20:
                    empty_files.append(str(f.relative_to(project_root)))
                elif "TODO" in text or "pass\n" in text or "NotImplementedError" in text:
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
        "main.py",
        "vault/crypto.py",
        "vault/storage.py",
        "vault/cli.py",
        "vault/models.py",
        "vault/generator.py",
        "requirements.txt",
        "tests/test_crypto.py",
    ]
    missing = [e for e in expected if not (project_root / e).exists()]
    if missing:
        print(f"\n[WARN] Expected files missing: {missing}")
    else:
        print("\n[OK] All expected files present")


if __name__ == "__main__":
    main()
