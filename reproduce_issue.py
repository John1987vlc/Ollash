import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from backend.core.containers import main_container


def test_project_generation():
    print("🚀 Starting project generation test...")

    # Ensure OLLASH_ROOT_DIR is set for testing
    os.environ["OLLASH_ROOT_DIR"] = ".ollash_test"
    test_root = Path(".ollash_test")
    if not test_root.exists():
        test_root.mkdir(parents=True)

    # Initialize container and wire it
    from backend.api.routers import ALL_ROUTER_MODULES

    main_container.wire(modules=ALL_ROUTER_MODULES + [__name__])

    # Get agent via DI
    agent = main_container.auto_agent_module.auto_agent()

    project_description = "un juego de ajedrez en html,js y css"
    project_name = "test_ajedrez"

    try:
        print(f"📝 Description: {project_description}")
        project_path = agent.run(project_description=project_description, project_name=project_name)
        print(f"✅ Project generated at: {project_path}")

        # Check if README.md exists and is not empty
        readme_path = project_path / "README.md"
        if readme_path.exists():
            content = readme_path.read_text(encoding="utf-8")
            print(f"📄 README.md size: {len(content)} chars")
            if len(content) < 100:
                print("⚠️ README.md seems too small!")
            else:
                print("👍 README.md looks good.")
                print("--- README PREVIEW ---")
                print(content[:500])
                print("----------------------")
        else:
            print("❌ README.md NOT FOUND!")

        # Check for other expected files
        files = list(project_path.glob("**/*"))
        print(f"Total files generated: {len(files)}")
        for f in files:
            if f.is_file():
                print(f"  - {f.relative_to(project_path)}")

    except Exception as e:
        print(f"❌ Error during generation: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_project_generation()
