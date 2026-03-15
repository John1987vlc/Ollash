"""Phase 8: FinishPhase — project summary, metrics, and completion event.

Writes OLLASH.md (generation summary) and .ollash/metrics.json.
No LLM calls. Publishes project_complete event.

Improvements:
  #11 — Generates README.md with a Mermaid architecture diagram derived from the blueprint
  #14 — OLLASH.md includes per-phase token breakdown table
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


class FinishPhase(BasePhase):
    phase_id = "8"
    phase_label = "Finish"

    def run(self, ctx: PhaseContext) -> None:
        # Write summary
        summary = self._build_summary(ctx)
        self._write_file(ctx, "OLLASH.md", summary)

        # #11 — Write README.md with Mermaid diagram (only if not already generated)
        if "README.md" not in ctx.generated_files:
            readme = self._build_readme(ctx)
            self._write_file(ctx, "README.md", readme)

        # Write metrics JSON
        metrics_path = ".ollash/metrics.json"
        metrics_content = json.dumps(ctx.metrics, indent=2)
        self._write_file(ctx, metrics_path, metrics_content)

        # Log final stats
        ctx.logger.info(f"[Finish] Project '{ctx.project_name}' complete")
        ctx.logger.info(f"[Finish] Files generated: {len(ctx.generated_files)}")
        ctx.logger.info(f"[Finish] Total tokens: {ctx.total_tokens():,}")
        if ctx.errors:
            ctx.logger.warning(f"[Finish] {len(ctx.errors)} non-fatal error(s)")

        # Fire completion event
        ctx.event_publisher.publish_sync(
            "project_complete",
            project_name=ctx.project_name,
            project_root=str(ctx.project_root),
            project_type=ctx.project_type,
            tech_stack=ctx.tech_stack,
            files_generated=len(ctx.generated_files),
            total_tokens=ctx.total_tokens(),
            errors=ctx.errors,
            metrics=ctx.metrics,
        )

    def _build_summary(self, ctx: PhaseContext) -> str:
        timings: Dict[str, float] = ctx.metrics.get("phase_timings", {})
        total_sec = sum(timings.values())

        files_by_type: Dict[str, int] = {}
        for path in ctx.generated_files:
            ext = Path(path).suffix.lower() or ".other"
            files_by_type[ext] = files_by_type.get(ext, 0) + 1

        lines = [
            f"# {ctx.project_name}",
            "",
            f"**Description:** {ctx.project_description[:300]}",
            f"**Type:** {ctx.project_type}",
            f"**Stack:** {', '.join(ctx.tech_stack)}",
            "",
            "## Generation Stats",
            f"- Files generated: {len(ctx.generated_files)}",
            f"- Total tokens used: {ctx.total_tokens():,}",
            f"- Total time: {total_sec:.0f}s",
            f"- Errors: {len(ctx.errors)}",
            f"- Description complexity: {ctx.metrics.get('description_complexity', 'N/A')}/10",
            "",
            "## Phase Timings",
        ]
        for phase_id, elapsed in sorted(timings.items()):
            lines.append(f"- Phase {phase_id}: {elapsed:.1f}s")

        # #14 — Per-phase token breakdown table
        token_usage: Dict[str, Dict[str, int]] = ctx.metrics.get("token_usage", {})
        if token_usage:
            lines += [
                "",
                "## Token Usage by Phase",
                "| Phase | Prompt | Completion | Total |",
                "|-------|--------|------------|-------|",
            ]
            for phase_id, usage in sorted(token_usage.items()):
                prompt = usage.get("prompt", 0)
                completion = usage.get("completion", 0)
                lines.append(f"| {phase_id} | {prompt:,} | {completion:,} | {prompt + completion:,} |")
            lines.append(f"| **Total** | | | **{ctx.total_tokens():,}** |")

        lines += ["", "## Files by Type"]
        for ext, count in sorted(files_by_type.items()):
            lines.append(f"- `{ext}`: {count}")

        if ctx.errors:
            lines += ["", "## Non-fatal Errors"]
            for err in ctx.errors:
                lines.append(f"- {err}")

        # Coherence warnings
        coh = ctx.metrics.get("coherence_warnings", [])
        if coh:
            lines += ["", "## Coherence Warnings"]
            for w in coh:
                lines.append(f"- {w}")

        return "\n".join(lines) + "\n"

    # ----------------------------------------------------------------
    # #11 — README with Mermaid architecture diagram
    # ----------------------------------------------------------------

    def _build_readme(self, ctx: PhaseContext) -> str:
        """Generate a README.md with project info and a Mermaid dependency diagram."""
        diagram = self._build_mermaid_diagram(ctx)
        usage = self._build_usage_section(ctx)

        lines = [
            f"# {ctx.project_name}",
            "",
            f"> {ctx.project_description[:300]}",
            "",
            f"**Type:** {ctx.project_type} | **Stack:** {', '.join(ctx.tech_stack)}",
            "",
            "## Architecture",
            "",
            "```mermaid",
            diagram,
            "```",
            "",
            "## Getting Started",
            "",
            usage,
            "",
            "---",
            f"*Generated by [Ollash](https://github.com/ollash) with {ctx.llm_manager.get_client('coder').model if hasattr(ctx.llm_manager.get_client('coder'), 'model') else 'Ollama'}*",  # noqa: E501
        ]
        return "\n".join(lines) + "\n"

    @staticmethod
    def _build_mermaid_diagram(ctx: PhaseContext) -> str:
        """Build a Mermaid flowchart TD from the blueprint import graph.

        Each file is a node; an arrow A --> B means A imports B.
        Node IDs are sanitized (slashes/dots replaced) to be valid Mermaid identifiers.
        """
        if not ctx.blueprint:
            return "graph TD\n    (no blueprint)"

        all_paths = {fp.path for fp in ctx.blueprint}
        lines: List[str] = ["graph TD"]

        # Create sanitized node ID mapping
        def node_id(path: str) -> str:
            return re.sub(r"[^a-zA-Z0-9_]", "_", path)

        import re

        # Declare all nodes with short labels
        for fp in ctx.blueprint:
            nid = node_id(fp.path)
            name = Path(fp.path).name
            lines.append(f'    {nid}["{name}"]')

        # Add edges (A --> B means A depends on B)
        for fp in ctx.blueprint:
            for dep in fp.imports:
                if dep in all_paths:
                    lines.append(f"    {node_id(fp.path)} --> {node_id(dep)}")

        return "\n".join(lines)

    @staticmethod
    def _build_usage_section(ctx: PhaseContext) -> str:
        """Generate basic usage instructions based on project type and tech stack."""
        ptype = ctx.project_type
        stack = ctx.tech_stack

        # Frontend / static
        if ptype in ("frontend_web", "web_app", "game"):
            return "Open `index.html` in your browser, or serve locally:\n\n```bash\nnpx serve . -l 8080\n```"

        # Python
        if "python" in stack:
            entry = next(
                (p for p in ("main.py", "app.py", "cli.py", "run.py", "server.py") if p in ctx.generated_files),
                "main.py",
            )
            return f"```bash\npip install -r requirements.txt\npython {entry}\n```"

        # Go
        if ptype == "go_service" or any(t in stack for t in ("go", "golang")):
            return "```bash\ngo mod tidy\ngo run .\n```"

        # Rust
        if ptype == "rust_project" or "rust" in stack:
            return "```bash\ncargo build\ncargo run\n```"

        # Java / Kotlin + Maven
        if ptype in ("java_app", "kotlin_app") or any(t in stack for t in ("java", "kotlin", "spring")):
            if any(p == "pom.xml" for p in ctx.generated_files):
                return "```bash\nmvn package\njava -jar target/*.jar\n```"
            return "```bash\n./gradlew build\njava -jar build/libs/*.jar\n```"

        # C# / .NET
        if ptype == "csharp_app" or any(t in stack for t in ("csharp", "dotnet", "c#")):
            return "```bash\ndotnet restore\ndotnet run\n```"

        # Flutter / Dart
        if ptype == "flutter_app" or any(t in stack for t in ("flutter", "dart")):
            return "```bash\nflutter pub get\nflutter run\n```"

        # PHP
        if ptype == "php_app" or "php" in stack:
            if any(p == "composer.json" for p in ctx.generated_files):
                return "```bash\ncomposer install\nphp -S localhost:8000\n```"
            return "```bash\nphp -S localhost:8000\n```"

        # Ruby
        if ptype == "ruby_app" or "ruby" in stack:
            entry = next(
                (p for p in ("app.rb", "main.rb", "server.rb") if p in ctx.generated_files),
                "app.rb",
            )
            if any(p == "Gemfile" for p in ctx.generated_files):
                return f"```bash\nbundle install\nruby {entry}\n```"
            return f"```bash\nruby {entry}\n```"

        # Node.js / TypeScript
        if "typescript" in stack or "javascript" in stack:
            return "```bash\nnpm install\nnpm start\n```"

        return "```bash\n# See individual files for setup instructions\n```"
