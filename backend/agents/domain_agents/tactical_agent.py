"""Tactical Agent — single-function implementation for small models.

F4: Abstraction Layers optimisation.

The TacticalAgent receives a single TaskNode describing ONE function to
implement. It:
1. Reads the target file from the Blackboard.
2. Extracts ONLY the function's line range via ``ast``.
3. Generates the implementation via LLM (minimal context — function stub only).
4. Applies it back using CodePatcher.apply_search_replace() so only the
   target function is touched and the rest of the file is preserved.
5. Validates with FileValidator.validate_syntax_immediate().
6. Writes back to Blackboard.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, List, TYPE_CHECKING

from backend.agents.domain_agents.base_domain_agent import BaseDomainAgent
from backend.utils.core.analysis.file_validator import FileValidator
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.event_publisher import EventPublisher
from backend.utils.domains.auto_generation.code_patcher import CodePatcher

if TYPE_CHECKING:
    from backend.agents.orchestrators.blackboard import Blackboard
    from backend.agents.orchestrators.task_dag import TaskNode
    from backend.agents.orchestrators.tool_dispatcher import ToolDispatcher


class TacticalAgent(BaseDomainAgent):
    """Implements a single named function inside an existing file.

    Designed for small models (<=4B) that struggle with full-file context.
    Receives a focused task and modifies ONLY the target function.
    """

    REQUIRED_TOOLS: List[str] = ["code_patcher"]
    agent_id: str = "tactical_0"

    def __init__(
        self,
        code_patcher: CodePatcher,
        file_validator: FileValidator,
        event_publisher: EventPublisher,
        logger: AgentLogger,
        tool_dispatcher: "ToolDispatcher",
        llm_client: Any = None,
    ) -> None:
        super().__init__(event_publisher, logger, tool_dispatcher)
        self._patcher = code_patcher
        self._validator = file_validator
        self._llm_client = llm_client

    def run(
        self,
        node: "TaskNode",
        blackboard: "Blackboard",
    ) -> Dict[str, Any]:
        """Implement the target function in the target file.

        ``node.task_data`` must contain:
        - ``file_path``: relative path of the file to edit.
        - ``function_name``: name of the function to implement.
        - ``plan``: dict with ``purpose`` and ``main_logic`` hints (optional).

        Returns:
            ``{file_path: updated_content, "context_note": note}``
        """
        file_path: str = node.task_data.get("file_path", "")
        function_name: str = node.task_data.get("function_name", "")

        if not file_path or not function_name:
            raise ValueError("TacticalAgent requires 'file_path' and 'function_name' in task_data")

        self._log_info(f"[Tactical] Implementing '{function_name}' in '{file_path}'")

        # 1. Read current file content from Blackboard
        current_content: str = blackboard.read(f"generated_files/{file_path}", "")
        if not current_content:
            raise RuntimeError(f"TacticalAgent: no content found for '{file_path}' on Blackboard")

        # 2. Extract the function stub (SEARCH block)
        search_block = self._extract_function_block(current_content, function_name)
        if not search_block:
            self._log_info(f"[Tactical] Function '{function_name}' not found — skipping")
            return {file_path: current_content, "context_note": f"Skipped: {function_name} not found"}

        # 3. Generate implementation via LLM (minimal context)
        replace_block = self._generate_implementation(file_path, function_name, search_block, node.task_data)
        if not replace_block or replace_block == search_block:
            self._log_info(f"[Tactical] No improvement generated for '{function_name}'")
            return {file_path: current_content, "context_note": f"No change: {function_name}"}

        # 4. Apply patch — only touches the target function
        patches = [(search_block, replace_block)]
        updated_content, failed = self._patcher.apply_search_replace(current_content, patches)
        if failed:
            self._log_info(f"[Tactical] Patch could not be applied for '{function_name}'")
            return {file_path: current_content, "context_note": f"Patch failed: {function_name}"}

        # 5. Validate syntax
        error = self._validator.validate_syntax_immediate(file_path, updated_content)
        if error:
            self._log_info(f"[Tactical] Syntax error after patch for '{function_name}': {error}")
            return {file_path: current_content, "context_note": f"Syntax error: {function_name}"}

        # 6. Write back to Blackboard
        blackboard.write_sync(f"generated_files/{file_path}", updated_content, self.agent_id)
        self._log_info(f"[Tactical] '{function_name}' implemented in '{file_path}'")

        # F5: context note for downstream tasks
        context_note = (
            f"Tactical implementation of {function_name} in {file_path}.\n"
            f"Only this function was modified; all other code is unchanged."
        )
        return {file_path: updated_content, "context_note": context_note}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_function_block(content: str, function_name: str) -> str:
        """Extract the source lines of *function_name* from *content* using ast."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return ""

        lines = content.splitlines(keepends=True)
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == function_name
                and hasattr(node, "end_lineno")
            ):
                start = node.lineno - 1  # 0-indexed
                end = node.end_lineno  # inclusive, 1-indexed -> exclusive in slice
                return "".join(lines[start:end])
        return ""

    def _generate_implementation(
        self,
        file_path: str,
        function_name: str,
        stub: str,
        task_data: Dict[str, Any],
    ) -> str:
        """Ask the LLM to implement *function_name* given its stub."""
        if self._llm_client is None:
            return ""

        plan = task_data.get("plan", {})
        purpose = plan.get("purpose", "")
        logic_hints = "\n".join(f"- {s}" for s in plan.get("main_logic", [])[:5])

        prompt = (
            f"Implement the following Python function stub completely.\n\n"
            f"FILE: {file_path}\n"
            f"FUNCTION: {function_name}\n"
            f"PURPOSE: {purpose}\n"
            f"LOGIC HINTS:\n{logic_hints}\n\n"
            f"STUB:\n{stub}\n\n"
            f"Return ONLY the fully implemented function (same indentation, no extra code)."
        )
        try:
            response_data, _ = self._llm_client.chat(
                messages=[
                    {"role": "system", "content": "You are a Python function implementation expert."},
                    {"role": "user", "content": prompt},
                ],
                tools=[],
                options_override={"temperature": 0.1},
            )
            raw = response_data.get("content", "").strip()
            # Strip markdown fences if present
            import re as _re

            match = _re.search(r"```(?:python)?\n(.*?)```", raw, _re.DOTALL)
            return match.group(1) if match else raw
        except Exception as exc:
            self._log_error(f"[Tactical] LLM call failed: {exc}")
            return ""
