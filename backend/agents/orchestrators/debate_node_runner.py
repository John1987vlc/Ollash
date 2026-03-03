"""
DebateNodeRunner — Multi-Agent Consensus via Structured Debate.

When the DAG contains a DEBATE node (``AgentType.DEBATE``), the orchestrator
delegates execution to this runner instead of a single agent.

Two agents are assigned opposing perspectives and take turns arguing until:
  a) Both agents reach the same conclusion (consensus detected), or
  b) ``max_rounds`` is exhausted (longest-running agent wins by default).

Each round publishes a ``debate_round_completed`` event so the frontend
can render a live split-screen debate view.

The final consensus text is returned as the node result and written to the
Blackboard under ``debate/{node_id}/consensus``.

Typical use cases:
    - Architecture decisions (PostgreSQL vs MongoDB)
    - Security vulnerability severity assessment (Critical vs High)
    - Complex bug diagnosis with conflicting hypotheses

Usage::

    runner = DebateNodeRunner(
        agent_a=developer_agent,
        agent_b=auditor_agent,
        event_publisher=event_publisher,
        logger=logger,
        max_rounds=3,
    )
    consensus = await runner.run(node, blackboard)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, List, Optional

from backend.utils.core.system.agent_logger import AgentLogger
from backend.utils.core.system.event_publisher import EventPublisher

if TYPE_CHECKING:
    from backend.agents.orchestrators.blackboard import Blackboard
    from backend.agents.orchestrators.task_dag import TaskNode


_CONSENSUS_KEYWORDS = [
    "i agree",
    "agreed",
    "consensus",
    "we should go with",
    "final decision",
    "both agree",
    "concuerdo",
    "de acuerdo",
    "decisión final",
]


class DebateNodeRunner:
    """
    Runs a structured multi-agent debate and returns the consensus result.

    Args:
        agent_a: First participant agent (e.g. DeveloperAgent).
        agent_b: Second participant agent (e.g. AuditorAgent).
        event_publisher: For emitting ``debate_round_completed`` events.
        logger: AgentLogger for structured logging.
        max_rounds: Maximum number of back-and-forth rounds (default 3).
    """

    def __init__(
        self,
        agent_a: Any,
        agent_b: Any,
        event_publisher: EventPublisher,
        logger: AgentLogger,
        max_rounds: int = 3,
    ) -> None:
        self._agent_a = agent_a
        self._agent_b = agent_b
        self._event_publisher = event_publisher
        self._logger = logger
        self._max_rounds = max_rounds

    async def run(self, node: "TaskNode", blackboard: "Blackboard") -> str:
        """Execute the debate and return the consensus string.

        Args:
            node: A DEBATE TaskNode. ``node.task_data["topic"]`` is the
                  question to debate. ``node.debate_rounds`` overrides
                  the default ``max_rounds`` if set.
            blackboard: Shared state — intermediate arguments are stored
                        under ``debate/{node.id}/round_{n}``.

        Returns:
            The consensus text, or the last agent_b argument if no consensus.
        """
        topic: str = node.task_data.get("topic", node.id)
        max_rounds: int = node.debate_rounds or self._max_rounds

        self._logger.info(f"[DebateNodeRunner] Starting debate on '{topic}' ({max_rounds} max rounds)")

        history: List[str] = []
        consensus: Optional[str] = None

        for round_num in range(1, max_rounds + 1):
            # Agent A argues
            arg_a = await self._get_argument(
                agent=self._agent_a,
                node=node,
                blackboard=blackboard,
                role="proponent",
                topic=topic,
                history=history,
                round_num=round_num,
            )
            history.append(f"Agent A (round {round_num}): {arg_a}")
            await blackboard.write(
                f"debate/{node.id}/round_{round_num}_a",
                arg_a,
                self._agent_a.agent_id,
            )
            await self._event_publisher.publish(
                "debate_round_completed",
                task_id=node.id,
                round=round_num,
                agent_role="proponent",
                agent_id=self._agent_a.agent_id,
                argument=arg_a,
            )

            # Agent B argues
            arg_b = await self._get_argument(
                agent=self._agent_b,
                node=node,
                blackboard=blackboard,
                role="opponent",
                topic=topic,
                history=history,
                round_num=round_num,
            )
            history.append(f"Agent B (round {round_num}): {arg_b}")
            await blackboard.write(
                f"debate/{node.id}/round_{round_num}_b",
                arg_b,
                self._agent_b.agent_id,
            )
            await self._event_publisher.publish(
                "debate_round_completed",
                task_id=node.id,
                round=round_num,
                agent_role="opponent",
                agent_id=self._agent_b.agent_id,
                argument=arg_b,
            )

            # Check for consensus
            if self._detect_consensus(arg_a, arg_b):
                consensus = arg_b  # Last statement is the agreed position
                self._logger.info(f"[DebateNodeRunner] Consensus reached in round {round_num}")
                break

        if consensus is None:
            # No consensus — use the final Agent B statement as the decision
            consensus = history[-1] if history else f"No consensus on: {topic}"
            self._logger.warning(
                f"[DebateNodeRunner] No consensus after {max_rounds} rounds — using final Agent B statement."
            )

        await blackboard.write(f"debate/{node.id}/consensus", consensus, "debate_runner")
        await self._event_publisher.publish(
            "debate_consensus_reached",
            task_id=node.id,
            consensus=consensus,
            rounds_taken=round_num if consensus else max_rounds,
        )

        return consensus

    async def _get_argument(
        self,
        agent: Any,
        node: "TaskNode",
        blackboard: "Blackboard",
        role: str,
        topic: str,
        history: List[str],
        round_num: int,
    ) -> str:
        """Invoke agent with debate context and return its argument text."""
        from backend.agents.orchestrators.task_dag import TaskNode as TN, AgentType

        debate_node = TN(
            id=f"{node.id}_debate_{role}_r{round_num}",
            agent_type=AgentType.DEVELOPER,
            task_data={
                **node.task_data,
                "debate_role": role,
                "debate_topic": topic,
                "debate_history": "\n".join(history[-6:]),  # Last 3 rounds context
                "debate_round": round_num,
            },
        )
        try:
            result = await asyncio.wait_for(
                agent.run(debate_node, blackboard),
                timeout=120.0,
            )
            if isinstance(result, dict):
                return str(next(iter(result.values()), ""))
            return str(result or "")
        except Exception as exc:
            self._logger.error(f"[DebateNodeRunner] Agent error in round {round_num}: {exc}")
            return f"[Agent error: {exc}]"

    @staticmethod
    def _detect_consensus(arg_a: str, arg_b: str) -> bool:
        """Return True if either argument contains consensus-signalling keywords."""
        combined = (arg_a + " " + arg_b).lower()
        return any(kw in combined for kw in _CONSENSUS_KEYWORDS)
