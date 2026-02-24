"""
Developer Agent — Parallel file code generation.

Responsibilities:
- Generate file content via EnhancedFileContentGenerator (with optional RAG).
- For small scaffolding files, batch generation via ParallelFileGenerator.
- Write files atomically via LockedFileManager.
- Publish ``file_generated`` event after each file (triggers AuditorAgent JIT).
- On FileValidator failure, delegate to SelfHealingLoop immediately.

Multiple DeveloperAgent instances may run concurrently (pool); each is
distinguished by an ``instance_id`` integer set at construction time.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from backend.agents.domain_agents.base_domain_agent import BaseDomainAgent
from backend.utils.core.io.locked_file_manager import LockedFileManager
from backend.utils.core.llm.parallel_generator import ParallelFileGenerator
from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.event_publisher import EventPublisher
from backend.utils.domains.auto_generation.code_patcher import CodePatcher
from backend.utils.domains.auto_generation.enhanced_file_content_generator import (
    EnhancedFileContentGenerator,
)

if TYPE_CHECKING:
    from backend.agents.orchestrators.blackboard import Blackboard
    from backend.agents.orchestrators.self_healing_loop import SelfHealingLoop
    from backend.agents.orchestrators.task_dag import TaskNode
    from backend.agents.orchestrators.tool_dispatcher import ToolDispatcher


# Files that should be generated as a batch (minimal content, no unique logic)
_SMALL_FILE_PATTERNS: tuple = (
    "__init__.py",
    "conftest.py",
    "setup.py",
    "py.typed",
    ".gitkeep",
    ".gitignore",
)


class DeveloperAgent(BaseDomainAgent):
    """
    DEVELOPER domain agent — one instance per pool slot.

    Attributes:
        agent_id: Identifies the pool slot (``developer_0``, ``developer_1``, …).
    """

    REQUIRED_TOOLS: List[str] = [
        "file_content_generator",
        "code_patcher",
        "rag_context_selector",
        "locked_file_manager",
    ]
    agent_id: str = "developer_0"

    def __init__(
        self,
        file_content_generator: EnhancedFileContentGenerator,
        code_patcher: CodePatcher,
        locked_file_manager: LockedFileManager,
        parallel_file_generator: ParallelFileGenerator,
        event_publisher: EventPublisher,
        logger: AgentLogger,
        tool_dispatcher: "ToolDispatcher",
        self_healing_loop: Optional["SelfHealingLoop"] = None,
        instance_id: int = 0,
    ) -> None:
        super().__init__(event_publisher, logger, tool_dispatcher)
        self._file_gen = file_content_generator
        self._code_patcher = code_patcher
        self._locked_file_manager = locked_file_manager
        self._parallel_gen = parallel_file_generator
        self._healing_loop = self_healing_loop
        self.agent_id = f"developer_{instance_id}"
        self._instance_id = instance_id

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def run(
        self,
        node: "TaskNode",
        blackboard: "Blackboard",
    ) -> Dict[str, str]:
        """Generate the file(s) described by *node*.

        Writes results to Blackboard under ``generated_files/{rel_path}``
        and publishes ``file_generated`` for each file.

        Returns:
            ``{rel_path: content}`` mapping.
        """
        file_path: str = node.task_data.get("file_path", "")
        plan: Dict[str, Any] = node.task_data.get("plan", {})
        is_remediation: bool = node.task_data.get("is_remediation", False)
        is_validation_fix: bool = node.task_data.get("is_validation_fix", False)
        prevention_tips: str = node.task_data.get("prevention_tips", "")
        remediation_actions: list = node.task_data.get("remediation_actions", [])

        self._log_info(
            f"Generating '{file_path}' "
            f"{'[REMEDIATION]' if is_remediation else ''}"
        )

        # Gather RAG context from already-generated files in Blackboard
        context_files: Dict[str, str] = self._get_context_files(
            file_path, node.task_data.get("context_deps", []), blackboard
        )

        # Choose generation strategy
        if is_validation_fix:
            content = await self._fix_validation(
                file_path=file_path,
                original_content=node.task_data.get("original_content", ""),
                validation_error=node.task_data.get("validation_error", ""),
                context_files=context_files,
            )
        elif self._is_small_file(file_path):
            # Batch strategy: use ParallelFileGenerator for efficiency
            content = await self._generate_small_file(file_path, plan, context_files)
        else:
            content = await self._generate_single_file(
                file_path=file_path,
                plan=plan,
                context_files=context_files,
                is_remediation=is_remediation,
                prevention_tips=prevention_tips,
                remediation_actions=remediation_actions,
                blackboard=blackboard,
            )

        if content is None:
            raise RuntimeError(
                f"DeveloperAgent failed to generate content for '{file_path}'"
            )

        # Write to Blackboard (async-safe)
        await blackboard.write(
            f"generated_files/{file_path}", content, self.agent_id
        )

        # Publish event — triggers AuditorAgent JIT audit
        self._event_publisher.publish(
            "file_generated",
            file_path=file_path,
            agent_id=self.agent_id,
            content=content,
            content_preview=content[:200],
            is_remediation=is_remediation,
        )

        self._log_debug(f"'{file_path}' generated ({len(content)} chars).")
        return {file_path: content}

    # ------------------------------------------------------------------
    # Generation strategies
    # ------------------------------------------------------------------

    async def _generate_single_file(
        self,
        file_path: str,
        plan: Dict[str, Any],
        context_files: Dict[str, str],
        is_remediation: bool = False,
        prevention_tips: str = "",
        remediation_actions: Optional[list] = None,
        blackboard: Optional["Blackboard"] = None,
    ) -> Optional[str]:
        """Generate a single file via EnhancedFileContentGenerator with fallback.

        When *blackboard* is supplied and the generator supports streaming, each
        token chunk is forwarded to ``blackboard.write_stream_chunk()`` so the
        frontend can render live output via SSE.
        """
        loop = asyncio.get_event_loop()

        effective_plan = dict(plan)
        if is_remediation and remediation_actions:
            effective_plan["remediation_actions"] = remediation_actions
        if prevention_tips:
            effective_plan["prevention_tips"] = prevention_tips

        # Strategy 1 (streaming): generate_file_with_plan_streaming()
        if blackboard is not None and hasattr(
            self._file_gen, "generate_file_with_plan_streaming"
        ):
            try:
                async def _on_chunk(chunk: str) -> None:
                    await blackboard.write_stream_chunk(file_path, chunk, self.agent_id)

                content = await self._file_gen.generate_file_with_plan_streaming(
                    file_path=file_path,
                    logic_plan=effective_plan,
                    project_description="",
                    readme="",
                    structure={},
                    related_files=context_files,
                    chunk_callback=_on_chunk,
                )
                if content:
                    return content
            except Exception as exc:
                self._log_error(
                    f"Streaming generation failed for '{file_path}': {exc}; falling back"
                )

        # Strategy 2 (sync): EnhancedFileContentGenerator.generate_file_with_plan()
        try:
            content = await loop.run_in_executor(
                None,
                lambda: self._file_gen.generate_file_with_plan(
                    file_path=file_path,
                    logic_plan=effective_plan,
                    project_description="",
                    readme="",
                    structure={},
                    related_files=context_files,
                ),
            )
            if content:
                return content
        except AttributeError:
            pass  # generator doesn't have this method
        except Exception as exc:
            self._log_error(f"generate_file_with_plan failed for '{file_path}': {exc}")

        # Strategy 3 (sync fallback): FileContentGenerator.generate_file()
        try:
            content = await loop.run_in_executor(
                None,
                lambda: self._file_gen.generate_file(
                    file_path=file_path,
                    context=context_files,
                    plan=effective_plan,
                ),
            )
            return content if content else None
        except Exception as exc:
            self._log_error(f"File generation fallback failed for '{file_path}': {exc}")
            return None

    async def _generate_small_file(
        self,
        file_path: str,
        plan: Dict[str, Any],
        context_files: Dict[str, str],
    ) -> Optional[str]:
        """Generate minimal scaffolding content for small files."""
        file_name = Path(file_path).name

        if file_name == "__init__.py":
            # Determine exports from plan if available
            exports: List[str] = plan.get("exports", [])
            if exports:
                lines = [f"from .{Path(file_path).parent.name} import {', '.join(exports)}\n"]
                return "".join(lines)
            return ""

        if file_name == "conftest.py":
            return (
                "import pytest\n\n\n@pytest.fixture\n"
                "def sample_fixture():\n    return {}\n"
            )

        if file_name in ("py.typed", ".gitkeep"):
            return ""

        if file_name == ".gitignore":
            return "__pycache__/\n*.pyc\n.env\n.venv/\ndist/\nbuild/\n*.egg-info/\n"

        if file_name == "setup.py":
            return (
                "from setuptools import setup, find_packages\n\n"
                "setup(name='project', version='0.1.0', packages=find_packages())\n"
            )

        # Fallback to regular generation
        return await self._generate_single_file(file_path, plan, context_files)

    async def _fix_validation(
        self,
        file_path: str,
        original_content: str,
        validation_error: str,
        context_files: Dict[str, str],
    ) -> Optional[str]:
        """Attempt to fix a file that failed FileValidator checks."""
        loop = asyncio.get_event_loop()
        try:
            fixed = await loop.run_in_executor(
                None,
                lambda: self._code_patcher.edit_existing_file(
                    existing_content=original_content,
                    improvement_instructions=f"Fix the following validation error: {validation_error}",
                    file_path=file_path,
                ),
            )
            return fixed if fixed else original_content
        except Exception as exc:
            self._log_error(f"Validation fix failed for '{file_path}': {exc}")
            return original_content

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_small_file(file_path: str) -> bool:
        return Path(file_path).name in _SMALL_FILE_PATTERNS

    def _get_context_files(
        self,
        file_path: str,
        context_dep_paths: List[str],
        blackboard: "Blackboard",
    ) -> Dict[str, str]:
        """Fetch already-generated dependency files from Blackboard for RAG."""
        context: Dict[str, str] = {}
        for dep_path in context_dep_paths:
            content = blackboard.read(f"generated_files/{dep_path}")
            if content:
                context[dep_path] = content
        return context
