"""Critic Agent — error pattern detection without LLM calls.

F4: Abstraction Layers optimisation.

The CriticAgent scans all generated files using the persistent
ErrorKnowledgeBase to surface known error patterns and prevention tips.
It does NOT call the LLM — it is a fast, deterministic post-generation
quality check.

Outputs per file are written to Blackboard under ``critique/{file_path}``
as a dict: ``{"file": path, "warnings": [prevention_tip, ...]}``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, TYPE_CHECKING

from backend.agents.domain_agents.base_domain_agent import BaseDomainAgent
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.event_publisher import EventPublisher

if TYPE_CHECKING:
    from backend.agents.orchestrators.blackboard import Blackboard
    from backend.agents.orchestrators.task_dag import TaskNode
    from backend.agents.orchestrators.tool_dispatcher import ToolDispatcher
    from backend.utils.core.memory.error_knowledge_base import ErrorKnowledgeBase


class CriticAgent(BaseDomainAgent):
    """Post-generation critic that surfaces known error patterns.

    Designed to run as a terminal node in the TaskDAG (depends on all
    DEVELOPER / TACTICAL nodes). Zero LLM calls — queries only
    ErrorKnowledgeBase.query_similar_errors().
    """

    REQUIRED_TOOLS: List[str] = []
    agent_id: str = "critic_0"

    def __init__(
        self,
        error_knowledge_base: "ErrorKnowledgeBase",
        event_publisher: EventPublisher,
        logger: AgentLogger,
        tool_dispatcher: "ToolDispatcher",
    ) -> None:
        super().__init__(event_publisher, logger, tool_dispatcher)
        self._ekb = error_knowledge_base

    def run(
        self,
        node: "TaskNode",
        blackboard: "Blackboard",
    ) -> Dict[str, Any]:
        """Scan all generated files and write critique reports to Blackboard.

        Returns:
            ``{"critique_count": N, "context_note": note}``
        """
        self._log_info("[Critic] Starting error pattern scan...")

        generated: Dict[str, str] = blackboard.get_all_generated_files()
        if not generated:
            self._log_info("[Critic] No generated files found — skipping")
            return {"critique_count": 0, "context_note": "No files to critique"}

        critique_count = 0
        total_warnings = 0

        for file_path, content in generated.items():
            if not content:
                continue
            language = self._infer_language(file_path)
            try:
                patterns = self._ekb.query_similar_errors(
                    file_path=file_path,
                    language=language,
                    max_results=3,
                )
            except Exception as exc:
                self._log_info(f"[Critic] EKB query failed for '{file_path}': {exc}")
                continue

            if not patterns:
                continue

            warnings = [p.prevention_tip for p in patterns if p.prevention_tip]
            if not warnings:
                continue

            report: Dict[str, Any] = {
                "file": file_path,
                "language": language,
                "warnings": warnings,
                "pattern_count": len(patterns),
            }
            blackboard.write_sync(f"critique/{file_path}", report, self.agent_id)
            self._log_info(f"[Critic] {file_path}: {len(warnings)} prevention tip(s) written")
            critique_count += 1
            total_warnings += len(warnings)

        self._event_publisher.publish_sync(
            "critic_scan_complete",
            agent_id=self.agent_id,
            files_scanned=len(generated),
            files_with_warnings=critique_count,
            total_warnings=total_warnings,
        )
        self._log_info(f"[Critic] Scan complete: {critique_count}/{len(generated)} files have warnings")

        context_note = (
            f"Critic scan complete. "
            f"{critique_count} files have known error patterns. "
            f"Check Blackboard under 'critique/' for prevention tips."
        )
        return {"critique_count": critique_count, "context_note": context_note}

    @staticmethod
    def _infer_language(file_path: str) -> str:
        """Infer language from file extension for EKB queries."""
        _EXT_MAP: Dict[str, str] = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".rb": "ruby",
            ".sh": "shell",
        }
        ext = Path(file_path).suffix.lower()
        return _EXT_MAP.get(ext, "unknown")
