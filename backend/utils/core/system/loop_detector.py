import json
from datetime import datetime, timedelta
from typing import Any, Dict, List

import numpy as np

from backend.utils.core.system.agent_logger import AgentLogger


class LoopDetector:
    """Detects semantic loops and stagnation in agent tool-calling sequences."""

    def __init__(
        self,
        logger: AgentLogger,
        embedding_client: Any,
        threshold: int = 3,
        similarity_threshold: float = 0.95,
        stagnation_timeout_minutes: int = 2,
    ):
        self.logger = logger
        self.embedding_client = embedding_client
        self.threshold = threshold
        self.similarity_threshold = similarity_threshold
        self.stagnation_timeout = timedelta(minutes=stagnation_timeout_minutes)

        self.history: List[Dict] = []
        self.last_meaningful_action_time: datetime = datetime.now()
        self.progress_score: float = 0.0

    def _get_action_embedding(self, action_data: Dict) -> List[float]:
        """Generates an embedding for a given action (tool call and its result)."""
        action_string = json.dumps(
            {
                "tool_name": action_data["tool_name"],
                "args": action_data["args"],
                "result": action_data["result"],
            },
            sort_keys=True,
        )

        try:
            return self.embedding_client.get_embedding(action_string)
        except Exception as e:
            self.logger.error(f"Failed to get embedding for action: {e}")
            return [0.0] * 384

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Calculates the cosine similarity between two vectors."""
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)

        dot_product = np.dot(vec1_np, vec2_np)
        norm_a = np.linalg.norm(vec1_np)
        norm_b = np.linalg.norm(vec2_np)

        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def record_action(self, tool_name: str, args: Dict, result: Any):
        """Records a tool action for loop detection analysis."""
        self.history.append(
            {
                "tool_name": tool_name,
                "args": args,
                "result": result,
                "timestamp": datetime.now(),
            }
        )

    def detect_loop(self) -> bool:
        """Detects loops based on semantic similarity and stagnation."""
        if len(self.history) < self.threshold:
            return False

        # F19: Don't trigger loop detection if the last tool was planning-related
        # because agents often refine plans multiple times legitimately.
        last_action = self.history[-1]
        if last_action["tool_name"] in ["plan_actions", "ask_user"]:
            self.logger.debug(f"Loop detection bypassed for tool: {last_action['tool_name']}")
            return False

        # Semantic similarity loop detection
        recent_actions = self.history[-self.threshold :]
        recent_embeddings = [self._get_action_embedding(a) for a in recent_actions]

        is_similar_streak = True
        for i in range(len(recent_embeddings) - 1):
            similarity = self._cosine_similarity(recent_embeddings[i], recent_embeddings[i + 1])
            if similarity < self.similarity_threshold:
                is_similar_streak = False
                break

        if is_similar_streak:
            self.logger.warning(
                f"Semantic loop detected! Agent performed {self.threshold} semantically similar actions consecutively."
            )
            return True

        # Stagnation detection
        if datetime.now() - self.last_meaningful_action_time > self.stagnation_timeout:
            self.logger.warning(f"Stagnation detected! No meaningful action for {self.stagnation_timeout}.")
            return True

        return False

    def update_progress(self, tool_name: str, tool_result: Dict):
        """Updates a heuristic progress score based on tool execution."""
        initial = self.progress_score

        if tool_result.get("ok", False):
            if tool_name == "select_agent_type":
                self.progress_score += 1.0
            elif tool_name == "plan_actions":
                self.progress_score += 0.5
            elif tool_name == "detect_user_intent":
                intent = tool_result.get("result", {}).get("intent")
                confidence = tool_result.get("result", {}).get("confidence", 0.0)
                if intent != "exploration" and confidence > 0.7:
                    self.progress_score += 0.3
                elif intent == "exploration" and confidence < 0.6:
                    self.progress_score -= 0.1
            else:
                self.progress_score += 0.1
        else:
            self.progress_score -= 0.2

        if abs(self.progress_score - initial) > 0.05:
            self.last_meaningful_action_time = datetime.now()

    def reset(self):
        """Resets loop detection state for a new conversation turn."""
        self.history.clear()
        self.last_meaningful_action_time = datetime.now()
        self.progress_score = 0.0
