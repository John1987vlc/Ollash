import sys
import shutil
import pytest
from pathlib import Path

# Añadir el raíz del proyecto al path
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(project_root))

from backend.agents.auto_agent import AutoAgent  # noqa: E402
from backend.core.containers import main_container  # noqa: E402


@pytest.mark.skip(reason="Slow integration test with complex multi-phase logic. Use for manual validation only.")
def test_poker_project_generation():
    print("=== INICIANDO TEST: GENERACION DE PROYECTO POKER (REACT + ASCII) ===")

    # Nombre y descripción del proyecto
    project_name = "poker_ascii_game"
    description = (
        "Juego de pocker sin usar imagenes solo con el codigo ascii html,js y css. Usar React para la interfaz."
    )

    # Limpiar carpeta de test anterior si existe
    test_projects_dir = project_root / "generated_projects" / "auto_agent_projects"
    target_dir = test_projects_dir / project_name
    if target_dir.exists():
        print(f"Limpiando directorio previo: {target_dir}")
        shutil.rmtree(target_dir)

    # Inicializar el contenedor de dependencias
    main_container.wire(modules=[__name__, "backend.agents.auto_agent"])

    try:
        # Obtener una instancia del AutoAgent a través del contenedor
        agent: AutoAgent = main_container.auto_agent_module.auto_agent()

        print(f"\n[MISSION]: {description}")

        # Llamada síncrona: el método gestiona su propio loop internamente
        print("\n--- PASO 1: GENERANDO ESTRUCTURA ---")
        blueprint = agent.generate_structure_only(
            description=description,
            project_name=project_name
        )

        print("\n[SUCCESS] ESTRUCTURA GENERADA CON EXITO")
        print(f"Tipo de proyecto: {blueprint.get('project_type')}")
        print(f"Stack tecnologico: {blueprint.get('tech_stack')}")

        print("\nArchivos a generar:")
        for f in blueprint.get("files", []):
            print(f"  - {f['path']} ({f['purpose']})")

    except Exception as e:
        print(f"\n[ERROR] ERROR DURANTE LA GENERACION: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_poker_project_generation()
