#!/usr/bin/env python3
"""
Code Agent CLI

Uso:
    python run_agent.py --chat
    python run_agent.py "instruccion"
    python run_agent.py --timeout 600
    python run_agent.py --auto
    python run_agent.py --model codellama:7b
    python run_agent.py --auto-create --project-description "Flask REST API" --project-name myapi
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.agents.default_agent import DefaultAgent

from backend.core.containers import main_container  # noqa: E402
from backend.agents.auto_agent import AutoAgent  # noqa: E402


def main():
    import argparse

    # Initialize colorama
    init(autoreset=True)

    # Wire the container for dependency injection
    main_container.wire(modules=[__name__, "backend.agents.auto_agent"])

    parser = argparse.ArgumentParser(description="Code Agent (Ollama Tool Calling)")
    # ... (parser arguments remain the same)
    parser.add_argument("--url", help="URL base de Ollama (ej: http://localhost:11434)")
    parser.add_argument("--model", help="Modelo a usar (ej: codellama:7b, mistral, llama3)")
    parser.add_argument("--timeout", type=int, help="Timeout en segundos")
    parser.add_argument("--chat", action="store_true", help="Modo chat interactivo")
    parser.add_argument("--auto", action="store_true", help="Auto confirmar acciones")
    parser.add_argument("--path", type=str, help="Ruta al directorio del proyecto (ej: ./sandbox/ventas)")
    parser.add_argument("--auto-create", action="store_true", help="Modo creacion autonoma de proyectos")
    parser.add_argument("--project-description", type=str, help="Descripcion del proyecto (para --auto-create)")
    parser.add_argument(
        "--project-name", type=str, default="auto_project", help="Nombre del proyecto (para --auto-create)"
    )
    parser.add_argument("instruction", nargs="?", help="Instrucción directa")
    args = parser.parse_args()

    if args.auto_create:
        description = args.project_description
        if not description:
            description = input("Enter project description: ").strip()
            if not description:
                print("No description provided. Exiting.")
                return

        try:
            # Instantiate AutoAgent via the DI container
            auto_agent: AutoAgent = main_container.auto_agent_module.auto_agent()
            path = auto_agent.run(project_description=description, project_name=args.project_name)
            print(f"\n{Fore.GREEN}Project created at: {path}{Style.RESET_ALL}")
        except Exception as e:
            print(f"\n{Fore.RED}An error occurred during project creation: {e}{Style.RESET_ALL}")
        return

    # DefaultAgent logic
    agent = DefaultAgent(project_root=args.path, auto_confirm=args.auto, base_path=project_root)

    # Overrides from CLI
    if args.url:
        agent.ollama.url = f"{args.url.rstrip('/')}/api/chat"
    if args.model:
        agent.ollama.model = args.model
    if args.timeout:
        agent.ollama.timeout = args.timeout

    print(f"{Fore.CYAN}{'=' * 60}")
    print(f"{Fore.BLUE}Code Agent - Ollama Tool Calling")
    print(f"{Style.DIM}URL: {agent.ollama.url}")
    print(f"{Style.DIM}Model: {agent.ollama.model}")
    print(f"{Style.DIM}Timeout: {agent.ollama.timeout}s")
    print(f"{Fore.CYAN}{'=' * 60}")
    sys.stdout.flush()

    if args.chat:
        agent.chat_mode()
    elif args.instruction:
        print(f"\n{Fore.YELLOW}Tú:{Style.RESET_ALL} {args.instruction}\n")
        sys.stdout.flush()
        response = agent.chat(args.instruction, auto_confirm=args.auto)
        print(f"\n{Fore.GREEN}Agente:{Style.RESET_ALL}")
        print(response)
    else:
        # If no other mode is specified, print help
        if not args.auto_create:
            parser.print_help()


if __name__ == "__main__":
    main()
