#!/usr/bin/env python3
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
from typing import Optional

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from backend.core.containers import main_container
from backend.utils.core.system.structured_logger import StructuredLogger
from backend.utils.core.system.agent_logger import AgentLogger

def setup_global_configs(args):
    """Apply global flags to the system configuration."""
    # Handle --debug
    log_level = "DEBUG" if args.debug else "INFO"
    
    # In a real enterprise app, we'd update the container or config loader here
    # For now, we'll ensure the .ollash directory exists
    ollash_dir = project_root / ".ollash"
    ollash_dir.mkdir(exist_ok=True)

async def cmd_agent(args):
    """Invoke the standard AutoAgent."""
    main_container.wire(modules=["backend.agents.auto_agent"])
    from backend.agents.auto_agent import AutoAgent
    
    try:
        agent: AutoAgent = main_container.auto_agent_module.auto_agent()
        print(f"[*] Starting AutoAgent for task: {args.task}")
        
        path = agent.run(
            project_description=args.task,
            project_name=args.name or "auto_project",
            include_docker=True
        )
        print(f"
[+] Project generated successfully at: {path}")
    except Exception as e:
        print(f"[-] Error in agent: {e}")
        sys.exit(1)

async def cmd_swarm(args):
    """Invoke Cowork swarm implementation."""
    from backend.utils.domains.bonus.cowork_impl import CoworkTools
    from backend.utils.core.llm.ollama_client import OllamaClient
    from backend.utils.core.io.documentation_manager import DocumentationManager
    
    # Setup dependencies (simplified for CLI)
    log_path = project_root / ".ollash" / "swarm.log"
    sl = StructuredLogger(log_path, "swarm")
    al = AgentLogger(sl, "SwarmCLI")
    
    # Using default ollama client from container if possible
    ollama_client = main_container.core.llm_client()
    doc_manager = DocumentationManager(project_root, al, None, {})
    workspace_path = project_root / ".ollash" / "knowledge_workspace"
    
    tools = CoworkTools(doc_manager, ollama_client, al, workspace_path)
    
    print(f"[*] Running swarm task: {args.task}")
    # Routing based on task keywords or just choosing a default
    if "log" in args.task.lower():
        result = tools.analyze_recent_logs()
    elif "summary" in args.task.lower() or "summarize" in args.task.lower():
        # Expecting a file name in task or as separate arg
        doc_name = args.task.split()[-1] # Simple heuristic
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
            if p.is_file() and p.suffix in ['.py', '.js', '.ts', '.go', '.rs', '.java']:
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
            pr_body="This PR was automatically generated by the Ollash AI Agent."
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
        "agent": "orchestrator"
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
        print("
--- EXTRACTED TEXT ---")
        print(result.extracted_text)
        print("----------------------")
        print(f"Confidence: {result.confidence:.2f}, Time: {result.processing_time_ms:.0f}ms")
    except Exception as e:
        print(f"[-] OCR failed: {e}")

async def cmd_benchmark(args):
    """Run model benchmarking."""
    # Adapting logic from legacy/auto_benchmark.py
    # For now, we'll try to import it if possible or run as subprocess
    print("[*] Starting Model Benchmarking suite...")
    legacy_path = project_root / "legacy" / "auto_benchmark.py"
    if legacy_path.exists():
        import subprocess
        subprocess.run([sys.executable, str(legacy_path)])
    else:
        print("[-] Benchmarking script not found in legacy/")

async def cmd_test_gen(args):
    """Generate multi-language tests."""
    from backend.utils.domains.auto_generation.multi_language_test_generator import MultiLanguageTestGenerator
    from backend.utils.core.llm.llm_response_parser import LLMResponseParser
    from backend.utils.core.command_executor import CommandExecutor
    
    al = AgentLogger(StructuredLogger(project_root / ".ollash" / "test_gen.log", "test_gen"), "TestGenCLI")
    ollama_client = main_container.core.llm_client()
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
        framework=None # Auto-detect
    )
    
    if test_content:
        output_file = file_path.parent / f"test_{file_path.name}"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(test_content)
        print(f"[+] Tests generated and saved to: {output_file}")
    else:
        print("[-] Failed to generate tests.")

def main():
    parser = argparse.ArgumentParser(
        prog="ollash",
        description="Ollash Enterprise CLI - AI IT Operations Assistant",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Global Flags
    parser.add_argument("--gpu-limit", type=float, help="GPU memory limit for rate limiter")
    parser.add_argument("--model-fallback", action="store_true", help="Enable automatic model routing")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # agent <task>
    agent_parser = subparsers.add_parser("agent", help="Invoke standard AutoAgent")
    agent_parser.add_argument("task", help="Project description or task")
    agent_parser.add_argument("--name", help="Project name")
    
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
    
    # benchmark
    subparsers.add_parser("benchmark", help="Run model benchmarking suite")
    
    # test-gen <file> --lang <lang>
    test_gen_parser = subparsers.add_parser("test-gen", help="Generate multi-language tests")
    test_gen_parser.add_argument("file", help="Source file to test")
    test_gen_parser.add_argument("--lang", help="Target language/framework")

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return

    setup_global_configs(args)
    
    loop = asyncio.get_event_loop()
    
    try:
        if args.command == "agent":
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
