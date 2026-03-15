"""Phase 8: FinishPhase — project summary, metrics, and completion event.

Writes OLLASH.md (generation summary) and .ollash/metrics.json.
No LLM calls. Publishes project_complete event.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from backend.agents.auto_agent_phases.base_phase import BasePhase
from backend.agents.auto_agent_phases.phase_context import PhaseContext


class FinishPhase(BasePhase):
    phase_id = "8"
    phase_label = "Finish"

    def run(self, ctx: PhaseContext) -> None:
        # Write summary
        summary = self._build_summary(ctx)
        self._write_file(ctx, "OLLASH.md", summary)

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
            "",
            "## Phase Timings",
        ]
        for phase_id, elapsed in sorted(timings.items()):
            lines.append(f"- Phase {phase_id}: {elapsed:.1f}s")

        lines += ["", "## Files by Type"]
        for ext, count in sorted(files_by_type.items()):
            lines.append(f"- `{ext}`: {count}")

        if ctx.errors:
            lines += ["", "## Non-fatal Errors"]
            for err in ctx.errors:
                lines.append(f"- {err}")

        return "\n".join(lines) + "\n"
