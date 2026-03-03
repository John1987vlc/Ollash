"""
Async Tool Dispatcher for Domain Agents.

Provides a registry-based, async-first dispatch layer so that domain agents
do not call tools directly.  Key capabilities:

- **fire_and_forget**: Heavy tools (SecurityScan, documentation) can be
  launched as background tasks that publish results via EventPublisher when
  done, without blocking the agent.
- **dispatch_batch**: Groups small tool calls (e.g. generating multiple
  __init__.py files) into chunked asyncio.gather() calls, reducing round-trips.
- **Observability**: Every dispatch publishes ``tool_dispatched``,
  ``tool_completed``, or ``tool_failed`` events so the UI / logs have full
  visibility.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.event_publisher import EventPublisher


class ToolDispatcher:
    """
    Async tool dispatcher with registry, fire-and-forget, and batching.

    Usage::

        dispatcher = ToolDispatcher(event_publisher, logger, max_batch_size=5)
        dispatcher.register_tool("my_tool", my_async_fn)

        # Blocking call
        result = await dispatcher.dispatch("my_tool", {"arg": "value"})

        # Fire and forget (e.g. security scan)
        await dispatcher.dispatch("security_scan", {"file": "x.py"},
                                  fire_and_forget=True)

        # Batch (multiple small generations)
        results = await dispatcher.dispatch_batch([
            ("gen_file", {"path": "__init__.py"}),
            ("gen_file", {"path": "conftest.py"}),
        ])
    """

    def __init__(
        self,
        event_publisher: EventPublisher,
        logger: AgentLogger,
        max_batch_size: int = 5,
    ) -> None:
        self._event_publisher = event_publisher
        self._logger = logger
        self._max_batch_size = max_batch_size
        self._registry: Dict[str, Callable[..., Any]] = {}

    # ------------------------------------------------------------------
    # Registry
    # ------------------------------------------------------------------

    def register_tool(self, name: str, fn: Callable[..., Any]) -> None:
        """Register an async callable under *name*.

        The callable must be an async coroutine function.
        """
        if not asyncio.iscoroutinefunction(fn):
            raise TypeError(f"Tool '{name}' must be an async coroutine function.")
        self._registry[name] = fn

    def is_registered(self, name: str) -> bool:
        return name in self._registry

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def dispatch(
        self,
        tool_name: str,
        args: Dict[str, Any],
        fire_and_forget: bool = False,
        callback: Optional[Callable[[Any], None]] = None,
    ) -> Optional[Any]:
        """Dispatch a single tool call.

        Args:
            tool_name: Registered tool name.
            args: Keyword arguments forwarded to the tool.
            fire_and_forget: If True, schedule as a background task and return
                None immediately (the tool will publish results when done).
            callback: Optional callable invoked with the result on success.

        Returns:
            Tool result, or None for fire-and-forget calls.

        Raises:
            KeyError: If *tool_name* is not registered.
        """
        if tool_name not in self._registry:
            raise KeyError(f"Tool not registered: {tool_name!r}")

        agent_id = args.get("_agent_id", "unknown")
        task_id = args.get("_task_id", "")

        await self._event_publisher.publish(
            "tool_dispatched",
            tool=tool_name,
            args={k: v for k, v in args.items() if not k.startswith("_")},
        )
        # P9 — Tool Belt UI: announce which tool is starting (for swimlane icons)
        await self._event_publisher.publish(
            "tool_execution_started",
            tool_name=tool_name,
            agent_id=agent_id,
            task_id=task_id,
        )

        if fire_and_forget:
            asyncio.create_task(self._execute_with_callback(tool_name, args, callback, agent_id, task_id))
            return None

        return await self._execute_with_callback(tool_name, args, callback, agent_id, task_id)

    async def dispatch_batch(
        self,
        tool_calls: List[Tuple[str, Dict[str, Any]]],
    ) -> List[Optional[Any]]:
        """Dispatch multiple tool calls, chunked by *max_batch_size*.

        Runs each chunk concurrently via asyncio.gather().  Failures in one
        call do not abort the others; failed slots return None.

        Args:
            tool_calls: List of (tool_name, args) tuples.

        Returns:
            List of results in the same order as the input, None for failures.
        """
        results: List[Optional[Any]] = [None] * len(tool_calls)
        chunks = [tool_calls[i : i + self._max_batch_size] for i in range(0, len(tool_calls), self._max_batch_size)]

        offset = 0
        for chunk in chunks:
            chunk_results = await asyncio.gather(
                *[self._execute_with_callback(name, args, None) for name, args in chunk],
                return_exceptions=True,
            )
            for i, res in enumerate(chunk_results):
                if isinstance(res, Exception):
                    self._logger.error(f"[ToolDispatcher] batch call {chunk[i][0]} failed: {res}")
                    results[offset + i] = None
                else:
                    results[offset + i] = res
            offset += len(chunk)

        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _execute_with_callback(
        self,
        tool_name: str,
        args: Dict[str, Any],
        callback: Optional[Callable[[Any], None]],
        agent_id: str = "unknown",
        task_id: str = "",
    ) -> Optional[Any]:
        start = time.monotonic()
        # Strip internal metadata keys before forwarding to the tool fn
        clean_args = {k: v for k, v in args.items() if not k.startswith("_")}
        try:
            fn = self._registry[tool_name]
            result = await fn(**clean_args)
            duration_ms = int((time.monotonic() - start) * 1000)
            await self._event_publisher.publish(
                "tool_completed",
                tool=tool_name,
                duration_ms=duration_ms,
            )
            # P9 — Tool Belt UI: announce tool completion with duration for tooltip
            await self._event_publisher.publish(
                "tool_execution_completed",
                tool_name=tool_name,
                agent_id=agent_id,
                task_id=task_id,
                duration_ms=duration_ms,
            )
            if callback is not None:
                try:
                    callback(result)
                except Exception as cb_exc:
                    self._logger.warning(f"[ToolDispatcher] callback for '{tool_name}' raised: {cb_exc}")
            return result
        except Exception as exc:
            self._logger.error(f"[ToolDispatcher] '{tool_name}' failed: {exc}")
            await self._event_publisher.publish("tool_failed", tool=tool_name, error=str(exc))
            await self._event_publisher.publish(
                "tool_execution_completed",
                tool_name=tool_name,
                agent_id=agent_id,
                task_id=task_id,
                duration_ms=int((time.monotonic() - start) * 1000),
                error=str(exc),
            )
            return None
