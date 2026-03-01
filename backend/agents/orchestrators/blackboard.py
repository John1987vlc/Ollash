"""
Blackboard — Shared In-Memory State for Domain Agents.

Implements the Blackboard architectural pattern:
- Domain agents write partial results under namespaced keys.
- Other agents read those results for RAG context, stability checks, etc.
- Subscriptions allow agents to react to specific key changes.
- Invalidation signals alert agents that cached data is stale.

All write / invalidate operations publish events through the existing
EventPublisher so that the rest of the Ollash UI (Kanban, logs) picks them up
automatically without any additional plumbing.
"""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.event_publisher import EventPublisher


@dataclass
class BlackboardEntry:
    """A single stored value with provenance metadata."""

    key: str
    value: Any
    agent_id: str
    version: int
    invalidated: bool = False


class Blackboard:
    """
    Shared in-memory state store for domain agents.

    Key namespaces (by convention):
        ``generated_files/{rel_path}``  — DeveloperAgent file outputs
        ``scan_results/{rel_path}``     — AuditorAgent scan results
        ``infra_files/{rel_path}``      — DevOpsAgent infrastructure outputs
        ``codebase_stable``             — Set to True by orchestrator when all
                                          DEVELOPER tasks complete
        ``task_dag``                    — TaskDAG produced by ArchitectAgent
        ``project_structure``           — Structure dict from ArchitectAgent
        ``project_description``         — Original user request
        ``project_name``                — Project name
        ``readme_content``              — README generated in planning

    Thread / coroutine safety:
        write() and invalidate() hold an asyncio.Lock.
        read() and snapshot() are lock-free (read-only access is safe in
        CPython due to the GIL, and we never mutate while iterating).
    """

    def __init__(
        self,
        event_publisher: EventPublisher,
        logger: AgentLogger,
    ) -> None:
        self._store: Dict[str, BlackboardEntry] = {}
        self._lock = asyncio.Lock()
        self._event_publisher = event_publisher
        self._logger = logger
        self._version_counter: int = 0

    # ------------------------------------------------------------------
    # Write / invalidate
    # ------------------------------------------------------------------

    async def write(self, key: str, value: Any, agent_id: str) -> None:
        """Store a value under *key*, incrementing the version counter.

        Publishes a ``blackboard_updated`` event that other agents or the UI
        can subscribe to.
        """
        async with self._lock:
            self._version_counter += 1
            entry = BlackboardEntry(
                key=key,
                value=value,
                agent_id=agent_id,
                version=self._version_counter,
                invalidated=False,
            )
            self._store[key] = entry

        self._event_publisher.publish(
            "blackboard_updated",
            key=key,
            agent_id=agent_id,
            version=self._version_counter,
        )
        self._logger.debug(f"[Blackboard] {agent_id} wrote '{key}' (v{self._version_counter})")

    async def invalidate(self, key: str, agent_id: str) -> None:
        """Mark a key as stale.  Subscribers receive a ``blackboard_invalidated`` event.

        Agents holding a cached copy of this key (e.g. a function signature used
        as RAG context) should refresh before their next LLM call.
        """
        async with self._lock:
            entry = self._store.get(key)
            if entry is not None:
                entry.invalidated = True

        self._event_publisher.publish(
            "blackboard_invalidated",
            key=key,
            agent_id=agent_id,
        )
        self._logger.debug(f"[Blackboard] {agent_id} invalidated '{key}'")

    # ------------------------------------------------------------------
    # Read (synchronous — safe, no lock needed)
    # ------------------------------------------------------------------

    def read(self, key: str, default: Any = None) -> Any:
        """Return the stored value, or *default* if missing / invalidated."""
        entry = self._store.get(key)
        if entry is None or entry.invalidated:
            return default
        return entry.value

    def read_prefix(self, prefix: str) -> Dict[str, Any]:
        """Return all non-invalidated entries whose key starts with *prefix*."""
        return {
            entry.key: entry.value
            for entry in self._store.values()
            if entry.key.startswith(prefix) and not entry.invalidated
        }

    # ------------------------------------------------------------------
    # Subscriptions (delegate to EventPublisher with key filtering)
    # ------------------------------------------------------------------

    def subscribe(self, key: str, callback: Callable[[str, Any], None]) -> Callable[[], None]:
        """Register *callback* to be called whenever *key* is updated.

        The callback signature is ``callback(key, new_value)``.

        Returns:
            A zero-argument callable that, when called, unregisters this
            subscription.  Callers should invoke it when the subscriber is
            destroyed to prevent memory leaks.
        """

        def _filter_callback(event_type: str, event_data: Dict[str, Any]) -> None:
            if event_data.get("key") == key:
                value = self.read(key)
                try:
                    callback(key, value)
                except Exception as exc:
                    self._logger.warning(f"[Blackboard] subscriber error for '{key}': {exc}")

        self._event_publisher.subscribe("blackboard_updated", _filter_callback)

        def _unsubscribe() -> None:
            self._event_publisher.unsubscribe("blackboard_updated", _filter_callback)

        return _unsubscribe

    def subscribe_prefix(self, prefix: str, callback: Callable[[str, Any], None]) -> Callable[[], None]:
        """Register *callback* for any key that starts with *prefix*.

        Returns:
            A zero-argument callable that unregisters this subscription.
        """

        def _filter_callback(event_type: str, event_data: Dict[str, Any]) -> None:
            k = event_data.get("key", "")
            if k.startswith(prefix):
                value = self.read(k)
                try:
                    callback(k, value)
                except Exception as exc:
                    self._logger.warning(f"[Blackboard] prefix subscriber error for '{k}': {exc}")

        self._event_publisher.subscribe("blackboard_updated", _filter_callback)

        def _unsubscribe() -> None:
            self._event_publisher.unsubscribe("blackboard_updated", _filter_callback)

        return _unsubscribe

    # ------------------------------------------------------------------
    # Snapshot / bridging
    # ------------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """Return a deep-copy of all non-invalidated entries.

        Used by ``SelfHealingLoop`` to create an isolated context snapshot
        for remediation agents so they don't mutate live state.
        """
        return {entry.key: copy.deepcopy(entry.value) for entry in self._store.values() if not entry.invalidated}

    def get_all_generated_files(self) -> Dict[str, str]:
        """Convenience method: return all entries written under generated_files/."""
        prefix_entries = self.read_prefix("generated_files/")
        # Keys are "generated_files/{rel_path}" — strip the prefix
        return {k[len("generated_files/") :]: v for k, v in prefix_entries.items()}

    # ------------------------------------------------------------------
    # Streaming (Point 4 — token streaming)
    # ------------------------------------------------------------------

    def write_stream_chunk(self, rel_path: str, chunk: str, agent_id: str) -> None:
        """Append a streaming token chunk to the live buffer for *rel_path*.

        Unlike ``write()``, this is synchronous and does NOT increment the
        global version counter — it is optimised for high-frequency, low-cost
        updates where every character counts more than consistency metadata.

        The ``blackboard_stream_chunk`` event is published so the frontend
        can append the chunk to the live code panel in real time.
        """
        key = f"streaming_files/{rel_path}"
        entry = self._store.get(key)
        if entry is None:
            entry = BlackboardEntry(
                key=key,
                value=chunk,
                agent_id=agent_id,
                version=0,
                invalidated=False,
            )
            self._store[key] = entry
        else:
            entry.value = (entry.value or "") + chunk

        self._event_publisher.publish(
            "blackboard_stream_chunk",
            rel_path=rel_path,
            chunk=chunk,
            agent_id=agent_id,
        )

    # ------------------------------------------------------------------
    # Serialisation helper (Point 2 — checkpointing)
    # ------------------------------------------------------------------

    def snapshot_serializable(self) -> Dict[str, Any]:
        """Like ``snapshot()`` but converts non-JSON-serialisable values to str.

        Used by ``CheckpointManager.save_dag()`` to persist the Blackboard
        alongside the TaskDAG without risking ``json.dumps`` failures on
        complex objects (TaskDAG instances, asyncio Locks, etc.).
        """
        result: Dict[str, Any] = {}
        for entry in self._store.values():
            if entry.invalidated:
                continue
            v = entry.value
            if not isinstance(v, (str, int, float, bool, list, dict, type(None))):
                v = str(v)
            elif isinstance(v, list):
                v = [x if isinstance(x, (str, int, float, bool, type(None))) else str(x) for x in v]
            result[entry.key] = v
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._store)

    def keys(self) -> List[str]:
        return [e.key for e in self._store.values() if not e.invalidated]
