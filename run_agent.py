#!/usr/bin/env python3
"""
Code Agent CLI

Uso:
    python run_agent.py --chat
    python run_agent.py "instruccion"
    python run_agent.py --timeout 600
    python run_agent.py --auto
    python run_agent.py --model codellama:7b
"""

from src.agents.code_agent import CodeAgent
from colorama import Fore, Style, init


def main():
    import argparse
    import sys

    # Inicializa colorama (clave para Windows)
    init(autoreset=True)

    parser = argparse.ArgumentParser(description="Code Agent (Ollama Tool Calling)")
    parser.add_argument("--url", help="URL base de Ollama (ej: http://localhost:11434)")
    parser.add_argument("--model", help="Modelo a usar (ej: codellama:7b, mistral, llama3)")
    parser.add_argument("--timeout", type=int, help="Timeout en segundos")
    parser.add_argument("--chat", action="store_true", help="Modo chat interactivo")
    parser.add_argument("--auto", action="store_true", help="Auto confirmar acciones")
    parser.add_argument("instruction", nargs="?", help="Instrucción directa")
    args = parser.parse_args()

    agent = CodeAgent()

    # Overrides por CLI
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

        response = agent.chat(
            args.instruction,
            auto_confirm=args.auto
        )

        print(f"\n{Fore.GREEN}Agente:{Style.RESET_ALL}")
        print(response)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
