
import sys
import shutil
import json
from pathlib import Path

# Añadir el raíz del proyecto al path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from backend.agents.auto_agent import AutoAgent
from backend.core.containers import main_container

def test_poker_project_generation():
    print("=== INICIANDO TEST: GENERACIÓN DE PROYECTO POKER (REACT + ASCII) ===")
    
    # Nombre y descripción del proyecto
    project_name = "poker_ascii_game"
    description = "Juego de pocker sin usar imagenes solo con el codigo ascii html,js y css. Usar React para la interfaz."
    
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
        print(f"[TEMPLATE]: react-frontend")
        
        # Llamada síncrona: el método gestiona su propio loop internamente
        print("\n--- PASO 1: GENERANDO README Y ESTRUCTURA ---")
        readme, structure = agent.generate_structure_only(
            project_description=description,
            project_name=project_name,
            template_name="react-frontend",
            python_version="3.12",
            license_type="MIT",
            include_docker=False
        )
        
        print("\n✅ ESTRUCTURA GENERADA CON ÉXITO")
        
        # Verificar que el README mencione ASCII
        if "ascii" in readme.lower():
            print("🎯 El agente ha captado el requisito de usar código ASCII.")
        else:
            print("⚠️ Advertencia: El README no menciona explícitamente ASCII.")

        # Mostrar una previsualización de la estructura
        print("\nEstructura de carpetas:")
        for folder in structure.get('folders', []):
            print(f"  / {folder['name']}")
            if 'files' in folder:
                for file in folder.get('files', []):
                    print(f"    - {file}")

    except Exception as e:
        print(f"\n❌ ERROR DURANTE LA GENERACIÓN: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_poker_project_generation()
