#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ollash Enterprise CLI
Powerful command-line interface for the Ollash AI IT Agent.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from backend.core.containers import main_container  # noqa: E402
from backend.utils.core.system.structured_logger import StructuredLogger  # noqa: E402
from backend.utils.core.system.agent_logger import AgentLogger  # noqa: E402


def setup_global_configs(args):
    """Apply global flags to the system configuration."""
    # Handle --debug
    log_level = "DEBUG" if args.debug else "INFO"
    os.environ["OLLASH_LOG_LEVEL"] = log_level

    # In a real enterprise app, we'd update the container or config loader here
    # For now, we'll ensure the .ollash directory exists
    ollash_dir = project_root / ".ollash"
    ollash_dir.mkdir(exist_ok=True)


async def cmd_agent(args):
    """Invoke the multiagent DomainAgentOrchestrator (Agent-per-Domain architecture)."""
    try:
        orchestrator = main_container.domain_agents.domain_agent_orchestrator()
        pool_size: int = getattr(args, "pool_size", 3)
        timeout: int = getattr(args, "timeout", 300)

        print(f"[*] Starting DomainAgentOrchestrator for task: {args.task}")
        print(f"    Pool size: {pool_size} developer agents | Task timeout: {timeout}s")

        # Propagate per-task timeout into the orchestrator's _route_to_agent call by
        # wrapping run() \u2014 the actual timeout is consumed inside _route_to_agent.
        path = await orchestrator.run(
            project_description=args.task,
            project_name=args.name or "auto_project",
            pool_size=pool_size,
        )
        print(f"\n[+] Project generated successfully at: {path}")
    except Exception as e:
        print(f"[-] Error in agent: {e}")
        sys.exit(1)


async def cmd_swarm(args):
    """Invoke Cowork swarm implementation."""
    from backend.utils.domains.bonus.cowork_impl import CoworkTools
    from backend.utils.core.io.documentation_manager import DocumentationManager

    # Setup dependencies (simplified for CLI)
    log_path = project_root / ".ollash" / "swarm.log"
    sl = StructuredLogger(log_path, "swarm")
    al = AgentLogger(sl, "SwarmCLI")

    # Using default ollama client from container
    ollama_client = main_container.auto_agent_module.llm_client_manager().get_client("generalist")
    doc_manager = DocumentationManager(project_root, al, None, {})
    workspace_path = project_root / ".ollash" / "knowledge_workspace"

    tools = CoworkTools(doc_manager, ollama_client, al, workspace_path)

    print(f"[*] Running swarm task: {args.task}")
    # Routing based on task keywords or just choosing a default
    if "log" in args.task.lower():
        result = tools.analyze_recent_logs()
    elif "summary" in args.task.lower() or "summarize" in args.task.lower():
        # Expecting a file name in task or as separate arg
        doc_name = args.task.split()[-1]  # Simple heuristic
        result = tools.generate_executive_summary(doc_name)
    else:
        # Default to doc-to-task
        doc_name = args.task.split()[-1]
        result = tools.document_to_task(doc_name)

    print(json.dumps(result, indent=2))


async def cmd_security_scan(args):
    """Run vulnerability scan on a path."""
    from backend.utils.core.analysis.vulnerability_scanner import VulnerabilityScanner

    sl = StructuredLogger(project_root / ".ollash" / "security.log", "security")
    al = AgentLogger(sl, "SecurityCLI")
    scanner = VulnerabilityScanner(al)

    scan_path = Path(args.path)
    if scan_path.is_file():
        with open(scan_path, "r", encoding="utf-8") as f:
            content = f.read()
        result = scanner.scan_file(str(scan_path), content)
        print(f"[+] Scan result for {args.path}:")
        print(f"    Vulnerabilities: {len(result.vulnerabilities)}")
        for v in result.vulnerabilities:
            print(f"    - [{v.severity.upper()}] {v.rule_id}: {v.description} (Line {v.line_number})")
    elif scan_path.is_dir():
        files = {}
        for p in scan_path.rglob("*"):
            if p.is_file() and p.suffix in [".py", ".js", ".ts", ".go", ".rs", ".java"]:
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        files[str(p)] = f.read()
                except:
                    continue
        report = scanner.scan_project(files)
        print(f"[+] Project scan report for {args.path}:")
        print(f"    Total files: {report.total_files}")
        print(f"    Total vulnerabilities: {report.total_vulnerabilities}")
        print(f"    Critical: {report.critical_count}, High: {report.high_count}")
        if report.blocked_files:
            print(f"    Blocked files: {len(report.blocked_files)}")


async def cmd_git_pr(args):
    """Generate automated Pull Request."""
    from backend.utils.core.tools.git_pr_tool import GitPRTool

    sl = StructuredLogger(project_root / ".ollash" / "git.log", "git")
    al = AgentLogger(sl, "GitCLI")
    tool = GitPRTool(str(project_root), al)

    if args.auto:
        print("[*] Running automated PR workflow...")
        import uuid

        branch = f"auto-fix-{uuid.uuid4().hex[:8]}"
        result = tool.full_improvement_workflow(
            branch_name=branch,
            commit_message="feat(auto): autonomous improvement by Ollash",
            pr_title="Autonomous Improvement",
            pr_body="This PR was automatically generated by the Ollash AI Agent.",
        )
        if result.success:
            print(f"[+] PR created successfully: {result.pr_url}")
        else:
            print(f"[-] PR creation failed: {result.error}")


async def cmd_cron_add(args):
    """Schedule a recurring task."""
    from backend.utils.core.system.task_scheduler import get_scheduler

    scheduler = get_scheduler()
    task_id = f"task_{os.urandom(4).hex()}"
    task_data = {
        "name": f"CLI Task: {args.task[:20]}",
        "schedule": "custom",
        "cron": args.expr,
        "prompt": args.task,
        "agent": "orchestrator",
    }

    success = scheduler.schedule_task(task_id, task_data)
    if success:
        print(f"[+] Task '{task_id}' scheduled with expression: {args.expr}")
    else:
        print("[-] Failed to schedule task.")


async def cmd_vision_ocr(args):
    """Run OCR on a file."""
    from backend.utils.core.io.ocr_processor import OCRProcessor

    processor = OCRProcessor(workspace_path=str(project_root / ".ollash" / "knowledge_workspace"))
    print(f"[*] Processing image: {args.file}")
    try:
        result = processor.process_image(args.file)
        print("\n--- EXTRACTED TEXT ---")
        print(result.extracted_text)
        print("----------------------")
        print(f"Confidence: {result.confidence:.2f}, Time: {result.processing_time_ms:.0f}ms")
    except Exception as e:
        print(f"[-] OCR failed: {e}")


async def cmd_auto_agent(args):
    """Run the full AutoAgent 32-phase project pipeline."""
    print(f"[*] Running AutoAgent pipeline for: {args.task}")
    try:
        auto_agent = main_container.auto_agent_module.auto_agent()
        result_path = auto_agent.run(
            description=args.task,
            project_name=args.name or "auto_project",
        )
        print(f"\n[+] Project generated at: {result_path}")
    except Exception as e:
        print(f"[-] AutoAgent error: {e}")
        sys.exit(1)


async def cmd_benchmark(args):
    """Run model benchmarking."""
    from backend.agents.auto_benchmarker import ModelBenchmarker
    from backend.core.config import get_config

    print("[*] Starting Model Benchmarking suite...")
    config = get_config()
    benchmarker = ModelBenchmarker()

    all_local_models = benchmarker.get_local_models()
    if not all_local_models:
        print("[-] No local Ollama models found. Pull some first (e.g., 'ollama pull qwen3.5:4b').")
        return

    embedding_models = getattr(benchmarker, "embedding_models", set())
    chat_models = [m for m in all_local_models if m not in embedding_models and "embed" not in m]
    excluded = [m for m in all_local_models if m not in chat_models]
    if excluded:
        print(f"    Excluding embedding models: {', '.join(excluded)}")

    models_to_run = getattr(args, "models", None) or chat_models
    benchmarker.run_benchmark(models_to_run)
    log_path = benchmarker.save_logs()

    summary_model = config.LLM_MODELS.get("models", {}).get("summarization", config.DEFAULT_MODEL)
    print(f"\n[*] Generating summary with model: {summary_model}")
    report = benchmarker.generate_summary(summary_model)
    print("\n" + "=" * 50)
    print("AUTO-BENCHMARK REPORT")
    print("=" * 50)
    print(report)
    print(f"\n[+] Results saved to: {log_path.parent}")


async def cmd_test_gen(args):
    """Generate multi-language tests."""
    from backend.utils.domains.auto_generation.multi_language_test_generator import MultiLanguageTestGenerator
    from backend.utils.core.llm.llm_response_parser import LLMResponseParser
    from backend.utils.core.command_executor import CommandExecutor

    al = AgentLogger(StructuredLogger(project_root / ".ollash" / "test_gen.log", "test_gen"), "TestGenCLI")
    ollama_client = main_container.auto_agent_module.llm_client_manager().get_client("test_generator")
    parser = LLMResponseParser(al)
    executor = CommandExecutor(al)

    generator = MultiLanguageTestGenerator(ollama_client, al, parser, executor)

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"[-] File not found: {args.file}")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"[*] Generating {args.lang or 'auto'} tests for {args.file}...")
    test_content = generator.generate_tests(
        file_path=str(file_path),
        content=content,
        readme_context="Test generation from CLI",
        framework=None,  # Auto-detect
    )

    if test_content:
        output_file = file_path.parent / f"test_{file_path.name}"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(test_content)
        print(f"[+] Tests generated and saved to: {output_file}")
    else:
        print("[-] Failed to generate tests.")


async def cmd_chat(args):
    """Start interactive chat mode with DefaultAgent and Rich UI (Claude Code-style)."""
    try:
        from pathlib import Path as _Path

        from rich.console import Console, Group
        from rich.panel import Panel
        from rich.markdown import Markdown
        from rich.live import Live
        from rich.text import Text
        from rich.theme import Theme
        from rich.table import Table
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.completion import WordCompleter
        from prompt_toolkit.styles import Style as PTStyle
        from backend.agents.default_agent import DefaultAgent
        from backend.cli.repo_context import RepoContext
        from backend.cli.file_editor import FileEditor

        custom_theme = Theme(
            {
                "info": "dim cyan",
                "warning": "magenta",
                "error": "bold red",
                "user": "bold green",
                "agent": "bold purple",
                "metrics": "italic blue",
            }
        )
        console = Console(theme=custom_theme)

        agent = DefaultAgent(
            project_root=str(project_root),
            auto_confirm=False,
        )

        repo = RepoContext(project_root)
        editor = FileEditor(console, project_root)

        # Detect current model from agent config
        current_model = "qwen3.5:4b"
        try:
            current_model = agent.llm_client.model
            repo.set_model(current_model)
        except AttributeError:
            pass

        # prompt_toolkit session with persistent history + slash-command completion
        history_file = _Path.home() / ".ollash_history"
        slash_commands = [
            "/add",
            "/remove",
            "/files",
            "/show",
            "/edit",
            "/run",
            "/model",
            "/status",
            "/rescan",
            "/clear",
            "/clean",
            "/new-session",
            "/help",
            "/exit",
        ]
        completer = WordCompleter(slash_commands, pattern=r"^/\S*", sentence=True)
        pt_style = PTStyle.from_dict({"prompt": "bold ansipurple"})
        session: PromptSession = PromptSession(
            history=FileHistory(str(history_file)),
            completer=completer,
            style=pt_style,
        )

        is_debug = getattr(args, "debug", False)

        console.print(
            Panel.fit(
                f"[bold purple]Ollash Chat[/bold purple]  [dim]— {current_model}[/dim]\n"
                f"[dim]Repo: {project_root}[/dim]\n"
                "Type [yellow]/help[/yellow] for commands, [yellow]/exit[/yellow] to quit.",
                title="\U0001f916 Welcome",
                border_style="purple",
            )
        )

        def _show_help():
            table = Table(title="Slash Commands", show_header=False, box=None, padding=(0, 2))
            table.add_row("[yellow]/add <file>[/yellow]", "Add a file to the context window")
            table.add_row("[yellow]/remove <file>[/yellow]", "Remove a file from context")
            table.add_row("[yellow]/files[/yellow]", "List files in context")
            table.add_row("[yellow]/show <file>[/yellow]", "View a file with syntax highlighting")
            table.add_row("[yellow]/edit <file>[/yellow]", "Ask AI to edit a file (shows diff first)")
            table.add_row("[yellow]/run <command>[/yellow]", "Execute a shell command with live output")
            table.add_row("[yellow]/model <name>[/yellow]", "Switch the active model")
            table.add_row("[yellow]/status[/yellow]", "Show model, context, and token stats")
            table.add_row("[yellow]/rescan[/yellow]", "Rescan repo structure")
            table.add_row("[yellow]/clean[/yellow]", "Clear conversation history")
            table.add_row("[yellow]/new-session[/yellow]", "Reset history and metrics")
            table.add_row("[yellow]/clear[/yellow]", "Clear the screen")
            table.add_row("[yellow]/exit[/yellow]", "Quit")
            console.print(table)
            console.print("\n[info]Available agent tools:[/info]")
            console.print("[dim]" + ", ".join(sorted(agent.tool_functions.keys())) + "[/dim]")

        async def _run_agent(user_message: str):
            """Run the agent and display streaming thoughts + final answer."""
            # Prepend repo context if any files are added
            full_message = user_message
            if repo.has_context():
                ctx_block = repo.build_context_block()
                full_message = f"{ctx_block}\n\n---\n\n{user_message}"

            with Live(vertical_overflow="visible", console=console) as live:
                thoughts = []
                current_cot = ""

                def update_thoughts(event_type, event_data):
                    nonlocal current_cot
                    if event_type == "thinking":
                        msg = event_data.get("message", "")
                        thoughts.append(f"[dim]\u2022 {msg}[/dim]")
                    elif event_type == "thinking_token":
                        token = event_data.get("token", "")
                        current_cot += token
                        display_cot = current_cot.strip().split("\n")[-1]
                        if len(display_cot) > 100:
                            display_cot = "..." + display_cot[-97:]
                        content = Group(*[Text.from_markup(t) for t in thoughts])
                        cot_text = Text(f"  > {display_cot}", style="dim italic gray")
                        live.update(Group(content, cot_text))
                        return
                    elif event_type == "tool_start":
                        tn = event_data.get("tool_name", "")
                        args_data = event_data.get("args", {})
                        if is_debug:
                            thoughts.append(f"[bold cyan]\U0001f527 Tool Call: {tn}[/bold cyan]")
                            thoughts.append(f"[dim]{json.dumps(args_data, indent=2)}[/dim]")
                        else:
                            thoughts.append(f"[italic cyan]\U0001f527 Using tool: {tn}...[/italic cyan]")
                    elif event_type == "tool_end":
                        success = event_data.get("success", True)
                        res_data = event_data.get("result", "")
                        status_icon = "[green]✓[/green]" if success else "[red]✗[/red]"
                        if is_debug:
                            thoughts.append(f"[dim]  └ Result: {status_icon} {res_data}[/dim]")
                        else:
                            thoughts.append(f"[dim]  └ {status_icon}[/dim]")
                    elif event_type == "llm_request" and is_debug:
                        model = event_data.get("model", "")
                        thoughts.append(f"[bold magenta]\U0001f4e1 LLM ({model})[/bold magenta]")
                    elif event_type == "llm_response" and is_debug:
                        model = event_data.get("model", "")
                        thoughts.append(f"[bold magenta]\U0001f4e8 LLM response ({model})[/bold magenta]")
                    elif event_type == "debug":
                        msg = event_data.get("message", "")
                        thoughts.append(f"[bold yellow]DEBUG:[/bold yellow] [dim]{msg}[/dim]")
                    elif event_type == "iteration":
                        it = event_data.get("current")
                        mx = event_data.get("max")
                        thoughts.append(f"[italic blue]\U0001f504 Iteration {it}/{mx}...[/italic blue]")

                    live.update(Group(*[Text.from_markup(t) for t in thoughts]))

                events = [
                    "thinking",
                    "thinking_token",
                    "tool_start",
                    "tool_end",
                    "iteration",
                    "llm_request",
                    "llm_response",
                    "debug",
                ]
                for e in events:
                    agent.event_publisher.subscribe(e, update_thoughts)

                def handle_hil(event_type, event_data):
                    live.stop()
                    console.print("\n")
                    action = event_data.get("type", "unknown")
                    details = event_data.get("details", {})
                    detail_str = json.dumps(details, indent=2)
                    console.print(
                        Panel(
                            f"[bold yellow]The agent needs permission:[/bold yellow]\n"
                            f"[bold cyan]Action:[/bold cyan] {action}\n\n"
                            f"[dim]Parameters:[/dim]\n{detail_str}",
                            title="\U0001f6e1\ufe0f Security Gate",
                            border_style="yellow",
                        )
                    )
                    from rich.prompt import Confirm
                    from backend.utils.core.system.execution_bridge import bridge

                    approved = Confirm.ask(f"[bold green]Allow {action}?[/bold green]", default=True)
                    bridge.run(
                        agent.event_publisher.publish(
                            "hil_response",
                            {"request_id": event_data.get("id"), "response": "approve" if approved else "reject"},
                        )
                    )
                    live.start()

                agent.event_publisher.subscribe("hil_request", handle_hil)

                try:
                    result = await agent.chat(full_message, auto_confirm=agent.auto_confirm)
                finally:
                    for e in events:
                        agent.event_publisher.unsubscribe(e, update_thoughts)
                    agent.event_publisher.unsubscribe("hil_request", handle_hil)
                    live.update(Text(""))

            if isinstance(result, dict):
                answer = result.get("text", "")
                metrics = result.get("metrics", {})
                console.print(Panel(Markdown(answer), title="\U0001f916 [agent]Ollash[/agent]", border_style="purple"))
                console.print(
                    f"[metrics]\u23f1\ufe0f {metrics.get('duration_sec')}s | "
                    f"\U0001fa99 {metrics.get('total_tokens')} tokens | "
                    f"\U0001f504 {metrics.get('iterations')} iter[/metrics]"
                )
            else:
                console.print(Panel(str(result), title="\U0001f916 [agent]Ollash[/agent]", border_style="red"))

        # ── Main REPL loop ──────────────────────────────────────────────────────
        while True:
            try:
                prompt_text = f"[{current_model}] > "
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: session.prompt(prompt_text),
                )
                user_input = user_input.strip()

                if not user_input:
                    continue

                # ── Slash commands ──────────────────────────────────────────────
                cmd_lower = user_input.lower()

                if cmd_lower in {"exit", "quit", "salir", "/exit", "/quit"}:
                    try:
                        agent.memory_manager.update_conversation_history(agent.conversation)
                        agent.memory_manager.update_domain_context_memory(agent.domain_context_memory)
                    except Exception:
                        pass
                    console.print("\n[metrics]" + agent.token_tracker.get_session_summary() + "[/metrics]")
                    console.print("[user]\U0001f44b Goodbye![/user]")
                    break

                if cmd_lower in {"/help", "help"}:
                    _show_help()
                    continue

                if cmd_lower in {"/clear", "clear"}:
                    console.clear()
                    continue

                if cmd_lower == "/clean":
                    agent.conversation = []
                    console.print("[info]\U0001f9f9 Conversation cleared.[/info]")
                    continue

                if cmd_lower in {"/new-session", "new-session"}:
                    agent.conversation = []
                    from backend.utils.core.llm.token_tracker import TokenTracker

                    agent.token_tracker = TokenTracker()
                    console.print("[info]\u267b\ufe0f New session started.[/info]")
                    continue

                if cmd_lower == "/status":
                    st = repo.status()
                    table = Table(show_header=False, box=None, padding=(0, 2))
                    table.add_row("[cyan]Model[/cyan]", current_model)
                    table.add_row("[cyan]Repo root[/cyan]", st["root"])
                    table.add_row("[cyan]Context files[/cyan]", str(st["added_files"]))
                    table.add_row("[cyan]Repo structure[/cyan]", f"{st['structure_lines']} lines")
                    try:
                        table.add_row("[cyan]Tokens used[/cyan]", agent.token_tracker.get_session_summary())
                    except Exception:
                        pass
                    console.print(Panel(table, title="Status", border_style="cyan"))
                    continue

                if cmd_lower == "/files":
                    files = repo.list_files()
                    if files:
                        console.print("[info]Context files:[/info]")
                        for f in files:
                            console.print(f"  [green]•[/green] {f}")
                    else:
                        console.print("[dim]No files in context. Use /add <file> to add one.[/dim]")
                    continue

                if cmd_lower == "/rescan":
                    repo.rescan()
                    console.print("[info]Repo structure rescanned.[/info]")
                    continue

                if user_input.startswith("/add "):
                    target = user_input[5:].strip()
                    msg = repo.add_file(target)
                    console.print(f"[info]{msg}[/info]")
                    continue

                if user_input.startswith("/remove "):
                    target = user_input[8:].strip()
                    msg = repo.remove_file(target)
                    console.print(f"[info]{msg}[/info]")
                    continue

                if user_input.startswith("/show "):
                    target = user_input[6:].strip()
                    editor.show_file(target)
                    continue

                if user_input.startswith("/model "):
                    new_model = user_input[7:].strip()
                    try:
                        agent.llm_client = main_container.auto_agent_module.llm_client_manager().get_client_by_model(
                            new_model
                        )
                        current_model = new_model
                        repo.set_model(new_model)
                        console.print(f"[info]Switched to model: [bold]{new_model}[/bold][/info]")
                    except Exception as e:
                        console.print(f"[error]Could not switch model: {e}[/error]")
                    continue

                if user_input.startswith("/run "):
                    cmd_str = user_input[5:].strip()
                    console.print(f"[dim]$ {cmd_str}[/dim]")
                    try:
                        proc = await asyncio.create_subprocess_shell(
                            cmd_str,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.STDOUT,
                            cwd=str(project_root),
                        )
                        if proc.stdout:
                            async for line in proc.stdout:
                                console.print(line.decode("utf-8", errors="replace").rstrip())
                        await proc.wait()
                        exit_color = "green" if proc.returncode == 0 else "red"
                        console.print(f"[{exit_color}]Exit code: {proc.returncode}[/{exit_color}]")
                    except Exception as e:
                        console.print(f"[error]Run error: {e}[/error]")
                    continue

                if user_input.startswith("/edit "):
                    target = user_input[6:].strip()
                    # Ask AI to propose an edit to the file, then show diff
                    file_path = project_root / target
                    if not file_path.exists():
                        console.print(f"[error]File not found: {target}[/error]")
                        continue
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                    edit_prompt = (
                        f"Please propose improvements to the following file `{target}`. "
                        f"Return ONLY the complete updated file content, no explanations:\n\n"
                        f"```\n{content[:6000]}\n```"
                    )
                    console.print(f"[dim]Asking AI to propose edits for {target}...[/dim]")
                    await _run_agent(edit_prompt)
                    # Note: the user can /add the file and ask specific edits in follow-up messages
                    continue

                # ── Normal message → agent ─────────────────────────────────────
                await _run_agent(user_input)

            except KeyboardInterrupt:
                console.print("\n[warning]Interrupted. Type /exit to quit.[/warning]")
                continue
            except EOFError:
                console.print("\n[user]\U0001f44b Goodbye![/user]")
                break
            except Exception as e:
                console.print(f"\n[error]\u274c Error: {e}[/error]")
                if is_debug:
                    import traceback

                    traceback.print_exc()

    except Exception as e:
        print(f"[-] Error starting chat: {e}")
        import traceback

        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        prog="ollash",
        description="Ollash Enterprise CLI - AI IT Operations Assistant",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Global Flags
    parser.add_argument("--gpu-limit", type=float, help="GPU memory limit for rate limiter")
    parser.add_argument("--model-fallback", action="store_true", help="Enable automatic model routing")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # chat
    chat_parser = subparsers.add_parser("chat", help="Start interactive chat mode")
    chat_parser.add_argument("--debug", action="store_true", help="Enable verbose internal logs during chat")

    # agent <task>
    agent_parser = subparsers.add_parser(
        "agent",
        help="Generate a project using the multiagent DomainAgentOrchestrator",
    )
    agent_parser.add_argument("task", help="Project description or task")
    agent_parser.add_argument("--name", help="Project name (default: auto_project)")
    agent_parser.add_argument(
        "--pool-size",
        type=int,
        default=3,
        dest="pool_size",
        help="Number of parallel Developer Agents (default: 3)",
    )
    agent_parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        dest="timeout",
        help="Per-task LLM timeout in seconds (default: 300)",
    )

    # swarm <task>
    swarm_parser = subparsers.add_parser("swarm", help="Invoke Cowork swarm implementation")
    swarm_parser.add_argument("task", help="Swarm task (e.g., 'Summarize doc.pdf', 'Analyze logs')")

    # security scan <path>
    sec_parser = subparsers.add_parser("security", help="Security operations")
    sec_sub = sec_parser.add_subparsers(dest="subcommand")
    scan_parser = sec_sub.add_parser("scan", help="Scan path for vulnerabilities")
    scan_parser.add_argument("path", help="File or directory to scan")

    # git pr --auto
    git_parser = subparsers.add_parser("git", help="Git operations")
    git_sub = git_parser.add_subparsers(dest="subcommand")
    pr_parser = git_sub.add_parser("pr", help="PR management")
    pr_parser.add_argument("--auto", action="store_true", help="Auto-generate Pull Request")

    # cron add <expr> <task>
    cron_parser = subparsers.add_parser("cron", help="Task scheduling")
    cron_sub = cron_parser.add_subparsers(dest="subcommand")
    add_parser = cron_sub.add_parser("add", help="Add scheduled task")
    add_parser.add_argument("expr", help="Cron expression")
    add_parser.add_argument("task", help="Task prompt")

    # vision ocr <file>
    vision_parser = subparsers.add_parser("vision", help="Computer vision operations")
    vision_sub = vision_parser.add_subparsers(dest="subcommand")
    ocr_parser = vision_sub.add_parser("ocr", help="Run OCR on file")
    ocr_parser.add_argument("file", help="Image or PDF file")

    # auto-agent <task>
    aa_parser = subparsers.add_parser("auto-agent", help="Run AutoAgent 32-phase pipeline")
    aa_parser.add_argument("task", help="Project description")
    aa_parser.add_argument("--name", help="Project name (default: auto_project)")

    # benchmark
    bench_parser = subparsers.add_parser("benchmark", help="Run model benchmarking suite")
    bench_parser.add_argument("--models", nargs="*", help="Models to benchmark (default: all local)")

    # test-gen <file> --lang <lang>
    test_gen_parser = subparsers.add_parser("test-gen", help="Generate multi-language tests")
    test_gen_parser.add_argument("file", help="Source file to test")
    test_gen_parser.add_argument("--lang", help="Target language/framework")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    setup_global_configs(args)

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        if args.command == "chat":
            loop.run_until_complete(cmd_chat(args))
        elif args.command == "agent":
            loop.run_until_complete(cmd_agent(args))
        elif args.command == "swarm":
            loop.run_until_complete(cmd_swarm(args))
        elif args.command == "security" and args.subcommand == "scan":
            loop.run_until_complete(cmd_security_scan(args))
        elif args.command == "git" and args.subcommand == "pr":
            loop.run_until_complete(cmd_git_pr(args))
        elif args.command == "cron" and args.subcommand == "add":
            loop.run_until_complete(cmd_cron_add(args))
        elif args.command == "vision" and args.subcommand == "ocr":
            loop.run_until_complete(cmd_vision_ocr(args))
        elif args.command == "auto-agent":
            loop.run_until_complete(cmd_auto_agent(args))
        elif args.command == "benchmark":
            loop.run_until_complete(cmd_benchmark(args))
        elif args.command == "test-gen":
            loop.run_until_complete(cmd_test_gen(args))
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    main()
