"""Viability Estimator Phase — token / time / cost estimation before generation.

Runs after StructureGenerationPhase and before LogicPlanningPhase so the user
can decide to simplify the project or split it into microservices *before* any
expensive LLM calls happen.

Token estimates use rough heuristics:
  • Config / manifest file  ≈  200 tokens
  • Source / logic file     ≈  800 tokens
  • Test file               ≈  500 tokens
  • Documentation file      ≈  300 tokens

Multiplied by the number of generation phases (≈18) the estimate gives a
ballpark for the total session token budget.

If the estimate exceeds ``LARGE_PROJECT_THRESHOLD`` (2 000 000 tokens) the
phase asks the user for confirmation before proceeding via the event system.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.agents.auto_agent_phases.base_phase import BasePhase

_TOKENS_BY_TYPE: Dict[str, int] = {
    "config": 200,
    "test": 500,
    "docs": 300,
    "source": 800,
}

_CONFIG_EXTS = frozenset({".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env", ".lock"})
_TEST_PATTERNS = ("test_", "_test.", "spec_", ".spec.", "_spec.", "conftest")
_DOCS_EXTS = frozenset({".md", ".txt", ".rst"})
_GENERATION_PHASES = 18  # approximate number of content-generating phases
_LARGE_PROJECT_THRESHOLD = 2_000_000  # tokens


class ViabilityEstimatorPhase(BasePhase):
    """Phase 2.3: Viability and computational cost estimator."""

    phase_id = "2.3"
    phase_label = "Viability & Cost Estimator"

    async def run(
        self,
        project_description: str,
        project_name: str,
        project_root: Path,
        readme_content: str,
        initial_structure: Dict[str, Any],
        generated_files: Dict[str, str],
        file_paths: List[str],
        **kwargs: Any,
    ) -> Tuple[Dict[str, str], Dict[str, Any], List[str]]:
        all_paths = file_paths or list(initial_structure.keys())
        if not all_paths:
            all_paths = self._extract_paths_from_structure(initial_structure)

        report = self._estimate(all_paths)
        self.context.viability_report = report

        self.context.logger.info(
            f"[Viability] Estimated {report['total_files']} file(s), "
            f"~{report['estimated_tokens']:,} tokens, "
            f"~{report['estimated_minutes']:.1f} min."
        )

        # Publish for Web UI progress display
        await self.context.event_publisher.publish(
            "viability_estimate",
            project_name=project_name,
            **report,
        )

        # Ask user confirmation only for very large projects
        if report["estimated_tokens"] > _LARGE_PROJECT_THRESHOLD:
            self.context.logger.warning(
                f"[Viability] Large project: ~{report['estimated_tokens']:,} tokens "
                f"across {report['total_files']} files."
            )
            confirmed = await self._ask_confirmation(report, project_name)
            if not confirmed:
                from backend.utils.core.exceptions import PipelinePhaseError  # noqa: PLC0415

                raise PipelinePhaseError(
                    self.phase_name,
                    "User declined to proceed with a very large project. "
                    "Tip: split the project into smaller microservices.",
                )

        # Write report
        report_json = json.dumps(report, indent=2)
        self._write_file(
            project_root,
            "viability_report.json",
            report_json,
            generated_files,
            file_paths,
        )
        return generated_files, initial_structure, file_paths

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_file(file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        name = Path(file_path).name.lower()
        if ext in _CONFIG_EXTS:
            return "config"
        if ext in _DOCS_EXTS:
            return "docs"
        if any(p in name for p in _TEST_PATTERNS):
            return "test"
        return "source"

    def _estimate(self, file_paths: List[str]) -> Dict[str, Any]:
        breakdown: Dict[str, int] = {"config": 0, "test": 0, "docs": 0, "source": 0}
        for fp in file_paths:
            breakdown[self._classify_file(fp)] += 1

        tokens_per_phase = sum(count * _TOKENS_BY_TYPE[ftype] for ftype, count in breakdown.items())
        total_tokens = tokens_per_phase * _GENERATION_PHASES

        # Current session tokens from TokenTracker
        used_tokens = 0
        if self.context.token_tracker is not None:
            used_tokens = getattr(self.context.token_tracker, "session_total_tokens", 0)

        # Rough time estimate: assume 1000 tokens/second generation speed
        estimated_minutes = total_tokens / 60_000

        return {
            "total_files": len(file_paths),
            "breakdown": breakdown,
            "estimated_tokens": total_tokens,
            "tokens_used_so_far": used_tokens,
            "estimated_minutes": round(estimated_minutes, 1),
            "generation_phases": _GENERATION_PHASES,
            "threshold_exceeded": total_tokens > _LARGE_PROJECT_THRESHOLD,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    @staticmethod
    def _extract_paths_from_structure(structure: Dict[str, Any]) -> List[str]:
        """Flatten a nested {files: [], folders: [{name, files, folders}]} dict."""
        paths: List[str] = []

        def _walk(node: Dict[str, Any], prefix: str) -> None:
            for f in node.get("files", []):
                paths.append(f"{prefix}/{f}" if prefix else str(f))
            for folder in node.get("folders", []):
                name = folder.get("name", "")
                _walk(folder, f"{prefix}/{name}" if prefix else name)

        _walk(structure, "")
        return paths

    async def _ask_confirmation(self, report: Dict[str, Any], project_name: str) -> bool:
        """Publish a viability_confirmation_request and wait for a response."""
        import asyncio  # noqa: PLC0415
        import uuid  # noqa: PLC0415

        req_id = str(uuid.uuid4())[:8]
        event = asyncio.Event()
        answer_holder: Dict[str, bool] = {"approved": True}

        def _on_response(event_type: str, event_data: Dict) -> None:
            if event_data.get("request_id") == req_id:
                answer_holder["approved"] = bool(event_data.get("approved", True))
                event.set()

        try:
            self.context.event_publisher.subscribe("viability_confirmation_response", _on_response)
            await self.context.event_publisher.publish(
                "viability_confirmation_request",
                request_id=req_id,
                project_name=project_name,
                message=(
                    f"Project '{project_name}' is estimated at "
                    f"{report['estimated_tokens']:,} tokens across "
                    f"{report['total_files']} files "
                    f"(~{report['estimated_minutes']:.0f} min). "
                    "Consider splitting into microservices. Proceed anyway?"
                ),
                **report,
            )
            try:
                await asyncio.wait_for(event.wait(), timeout=300)
                return answer_holder["approved"]
            except asyncio.TimeoutError:
                self.context.logger.warning("[Viability] Confirmation timed out — proceeding.")
                return True
        except Exception as exc:
            self.context.logger.debug(f"[Viability] Confirmation error: {exc}")
            return True
        finally:
            try:
                self.context.event_publisher.unsubscribe("viability_confirmation_response", _on_response)
            except Exception:
                pass
