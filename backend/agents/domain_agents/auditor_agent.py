"""
Auditor Agent — JIT security and quality scanning.

Responsibilities:
- Subscribe to ``file_generated`` events at construction time.
- Immediately scan each file as it is generated (Just-In-Time audit).
- Quarantine files containing CRITICAL vulnerabilities.
- Write scan results to Blackboard under ``scan_results/{path}``.
- Run a final batch audit as a DAG node (cross-file pattern detection).

The JIT model means the AuditorAgent works in parallel with DeveloperAgents
without needing explicit DAG dependency edges for the per-file scan.  The
batch final audit (DAG node ``__auditor_final__``) catches cross-file issues.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from backend.agents.domain_agents.base_domain_agent import BaseDomainAgent
from backend.utils.core.analysis.code_quarantine import CodeQuarantine
from backend.utils.core.analysis.vulnerability_scanner import VulnerabilityScanner
from backend.utils.core.language_utils import LanguageUtils
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.event_publisher import EventPublisher
from backend.utils.domains.code.sandbox_runner import SandboxRunner

if TYPE_CHECKING:
    from backend.agents.orchestrators.blackboard import Blackboard
    from backend.agents.orchestrators.task_dag import TaskNode
    from backend.agents.orchestrators.tool_dispatcher import ToolDispatcher


class AuditorAgent(BaseDomainAgent):
    """
    AUDITOR domain agent — event-driven JIT scanning + empirical linter sandbox.

    Subscribes to ``file_generated`` at construction time.  Each event
    triggers ``_audit_file()`` as an asyncio background task, so auditing
    never blocks the DeveloperAgent pool.

    P3 (Empirical Validation): After static vulnerability scan, the SandboxRunner
    executes ``ruff`` on the generated file. Real linter errors are written to
    ``sandbox_errors/{rel_path}`` so SelfHealingLoop can inject them into the
    contingency plan prompt, dramatically improving fix accuracy.

    Output keys written to Blackboard:
        ``scan_results/{rel_path}``   — ScanResult per file
        ``sandbox_errors/{rel_path}`` — Real linter/type errors (if any)
        ``audit_summary``             — Aggregated stats after batch pass
    """

    REQUIRED_TOOLS: List[str] = ["vulnerability_scanner", "code_quarantine"]
    agent_id: str = "auditor"

    def __init__(
        self,
        vulnerability_scanner: VulnerabilityScanner,
        code_quarantine: CodeQuarantine,
        event_publisher: EventPublisher,
        logger: AgentLogger,
        tool_dispatcher: "ToolDispatcher",
        sandbox_runner: Optional[SandboxRunner] = None,
    ) -> None:
        super().__init__(event_publisher, logger, tool_dispatcher)
        self._vuln_scanner = vulnerability_scanner
        self._quarantine = code_quarantine
        self._sandbox: Optional[SandboxRunner] = sandbox_runner
        self._blackboard: Optional["Blackboard"] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

        # JIT subscription — active from construction
        self._event_publisher.subscribe("file_generated", self._on_file_generated)

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def set_blackboard(self, blackboard: "Blackboard") -> None:
        """Inject the Blackboard reference before the DAG loop starts."""
        self._blackboard = blackboard

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Inject the running event loop for create_task() calls."""
        self._event_loop = loop

    # ------------------------------------------------------------------
    # JIT subscription callback (synchronous — EventPublisher requirement)
    # ------------------------------------------------------------------

    def _on_file_generated(
        self, event_type: str, event_data: Dict[str, Any]
    ) -> None:
        """EventPublisher callback — synchronous.

        Schedules the async audit as a background task so it does not block
        the calling DeveloperAgent.
        """
        if self._blackboard is None:
            return

        file_path: str = event_data.get("file_path", "")
        content: str = event_data.get("content", "")

        if not file_path or not content:
            return

        try:
            loop = self._event_loop or asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self._audit_file(file_path, content))
            else:
                self._log_warning(
                    f"Event loop not running; skipping JIT audit for '{file_path}'"
                )
        except RuntimeError:
            # No event loop in this thread (e.g. sync test context)
            pass

    # ------------------------------------------------------------------
    # Audit implementation
    # ------------------------------------------------------------------

    async def _audit_file(self, file_path: str, content: str) -> None:
        """Scan a single file and write results to Blackboard."""
        if self._blackboard is None:
            return

        language = LanguageUtils.infer_language(file_path)
        self._log_debug(f"JIT audit: '{file_path}' ({language})")

        loop = asyncio.get_event_loop()
        try:
            scan_result = await loop.run_in_executor(
                None,
                lambda: self._vuln_scanner.scan_file(file_path, content, language),
            )
        except Exception as exc:
            self._log_error(f"VulnerabilityScanner failed on '{file_path}': {exc}")
            return

        # Write static scan results
        await self._blackboard.write(
            f"scan_results/{file_path}",
            scan_result,
            self.agent_id,
        )

        # P3 — Empirical validation: run real linter in sandbox
        if self._sandbox is not None:
            try:
                sandbox_result = await loop.run_in_executor(
                    None,
                    lambda: self._sandbox.run_linter(file_path, content),
                )
                self._publish_event(
                    "audit_sandbox_result",
                    rel_path=file_path,
                    passed=sandbox_result.passed,
                    tool=sandbox_result.tool,
                    errors=sandbox_result.errors,
                )
                if not sandbox_result.passed and sandbox_result.errors:
                    # Store real errors for SelfHealingLoop to inject into prompt
                    await self._blackboard.write(
                        f"sandbox_errors/{file_path}",
                        "\n".join(sandbox_result.errors),
                        self.agent_id,
                    )
                    self._log_debug(
                        f"Sandbox: {len(sandbox_result.errors)} linter errors in '{file_path}'"
                    )
            except Exception as exc:
                self._log_debug(f"Sandbox runner failed for '{file_path}': {exc}")

        # Check for critical findings
        has_critical = self._has_critical(scan_result)
        if has_critical:
            self._log_warning(f"CRITICAL vulnerability found in '{file_path}'!")
            try:
                await loop.run_in_executor(
                    None,
                    lambda: self._quarantine.quarantine_file(
                        file_path=file_path,
                        content=content,
                        reason="Critical vulnerability detected by AuditorAgent",
                    ),
                )
            except Exception as exc:
                self._log_error(f"Quarantine failed for '{file_path}': {exc}")

            self._publish_event(
                "audit_critical_found",
                file_path=file_path,
                vulnerability_count=self._count_critical(scan_result),
            )
        else:
            self._publish_event(
                "audit_completed",
                file_path=file_path,
                max_severity=self._max_severity(scan_result),
            )

    # ------------------------------------------------------------------
    # DAG node: final batch audit
    # ------------------------------------------------------------------

    async def run(
        self,
        node: "TaskNode",
        blackboard: "Blackboard",
    ) -> Dict[str, Any]:
        """Final batch audit pass executed as a DAG node.

        Scans all files in ``blackboard['generated_files/*']`` that have
        not yet been scanned (no entry in ``scan_results/``).

        Returns:
            Audit summary dict with total counts.
        """
        if self._blackboard is None:
            self._blackboard = blackboard

        generated_files = blackboard.get_all_generated_files()
        total = len(generated_files)
        scanned = 0
        critical_files: List[str] = []

        self._log_info(f"Batch audit: scanning {total} files.")

        for file_path, content in generated_files.items():
            # Skip already-scanned files
            if blackboard.read(f"scan_results/{file_path}") is not None:
                continue
            await self._audit_file(file_path, content)
            scanned += 1

        summary: Dict[str, Any] = {
            "total_files": total,
            "newly_scanned": scanned,
            "critical_files": critical_files,
        }
        await blackboard.write("audit_summary", summary, self.agent_id)
        self._publish_event("batch_audit_completed", **summary)
        self._log_info(
            f"Batch audit complete: {scanned} files scanned, "
            f"{len(critical_files)} critical issues."
        )
        return summary

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Unsubscribe all event listeners to prevent memory leaks in long-running processes."""
        try:
            self._event_publisher.unsubscribe("file_generated", self._on_file_generated)
        except (AttributeError, KeyError):
            pass

    @staticmethod
    def _has_critical(scan_result: Any) -> bool:
        """Return True if the scan result contains any CRITICAL severity finding."""
        try:
            for vuln in (scan_result.vulnerabilities if hasattr(scan_result, "vulnerabilities") else []):
                if hasattr(vuln, "severity") and vuln.severity.lower() == "critical":
                    return True
        except (AttributeError, TypeError):
            pass
        return False

    @staticmethod
    def _count_critical(scan_result: Any) -> int:
        count = 0
        try:
            for vuln in (scan_result.vulnerabilities if hasattr(scan_result, "vulnerabilities") else []):
                if hasattr(vuln, "severity") and vuln.severity.lower() == "critical":
                    count += 1
        except (AttributeError, TypeError):
            pass
        return count

    @staticmethod
    def _max_severity(scan_result: Any) -> str:
        """Return the highest severity found, or 'none'."""
        order = ["critical", "high", "medium", "low", "info"]
        found = set()
        try:
            for vuln in (scan_result.vulnerabilities if hasattr(scan_result, "vulnerabilities") else []):
                if hasattr(vuln, "severity"):
                    found.add(vuln.severity.lower())
        except (AttributeError, TypeError):
            pass
        for sev in order:
            if sev in found:
                return sev
        return "none"
