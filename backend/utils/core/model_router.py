import asyncio
import json
from typing import Any, Dict, List, Optional, Tuple

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.event_publisher import EventPublisher
from backend.utils.core.llm_response_parser import LLMResponseParser
from backend.utils.core.ollama_client import OllamaClient


class ModelRouter:
    """
    Routes prompts to specialist models, aggregates responses, and uses a Senior Reviewer
    to select the best solution (or combines them).
    """

    def __init__(
        self,
        llm_clients: Dict[str, OllamaClient],
        logger: AgentLogger,
        response_parser: LLMResponseParser,
        event_publisher: EventPublisher,
        senior_reviewer_model_name: str,
        config: Dict[str, Any],
    ):
        self.llm_clients = llm_clients
        self.logger = logger
        self.parser = response_parser
        self.event_publisher = event_publisher
        self.senior_reviewer_model_name = senior_reviewer_model_name
        self.config = config

        if self.senior_reviewer_model_name not in self.llm_clients:
            raise ValueError(f"Senior reviewer model '{self.senior_reviewer_model_name}' not found in llm_clients.")
        self.senior_reviewer_client = self.llm_clients[self.senior_reviewer_model_name]

    async def aroute_and_aggregate(
        self,
        messages: List[Dict],
        candidate_model_roles: List[str],
        tool_definitions: List[Dict],
        user_prompt_for_reviewer: str,  # A specific user prompt for the reviewer to evaluate
        task_description: str,  # Description of the task being performed
        options_override: Optional[Dict] = None,
    ) -> Tuple[Dict, List[Tuple[str, Dict]]]:
        """
        Asynchronously routes the prompt to multiple candidate models, aggregates their responses,
        and uses a Senior Reviewer to pick the best or synthesize.

        Returns the chosen response and a list of all raw candidate responses.
        """
        candidate_responses: List[Tuple[str, Dict]] = []  # (model_role, raw_response_data)

        tasks = []
        roles_in_task_order = []
        for role in candidate_model_roles:
            if role not in self.llm_clients:
                self.logger.warning(f"Model client for role '{role}' not found. Skipping.")
                continue

            roles_in_task_order.append(role)
            client = self.llm_clients[role]
            self.logger.info(f"  Routing prompt to specialist model: {role} ({client.model})")
            self.event_publisher.publish("tool_start", tool_name="model_router", model=client.model, role=role)
            tasks.append(
                client.achat(
                    messages=messages,
                    tools=tool_definitions,
                    options_override=options_override,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, role in enumerate(roles_in_task_order):
            result = results[i]
            client = self.llm_clients[role]
            if isinstance(result, Exception):
                self.logger.error(f"  Error getting response from model {client.model} (role: {role}): {result}")
                self.event_publisher.publish(
                    "tool_output",
                    tool_name="model_router",
                    model=client.model,
                    role=role,
                    status="error",
                    message=str(result),
                )
            else:
                response_data, usage = result
                candidate_responses.append((role, response_data))
                self.event_publisher.publish(
                    "tool_output",
                    tool_name="model_router",
                    model=client.model,
                    role=role,
                    status="success",
                    content=response_data["message"].get("content", "")[:200],
                )
            self.event_publisher.publish("tool_end", tool_name="model_router", model=client.model, role=role)

        if not candidate_responses:
            raise RuntimeError("No candidate models provided a response.")

        if len(candidate_responses) == 1:
            self.logger.info("  Only one candidate response. Skipping senior review.")
            return candidate_responses[0][1], candidate_responses

        self.logger.info("  Multiple candidate responses. Invoking Senior Reviewer to select the best.")
        self.event_publisher.publish(
            "tool_start",
            tool_name="senior_reviewer_selection",
            reviewer_model=self.senior_reviewer_client.model,
        )

        # Prepare messages for the Senior Reviewer
        reviewer_messages = [
            {"role": "system", "content": self._get_senior_reviewer_system_prompt()},
            {
                "role": "user",
                "content": user_prompt_for_reviewer,
            },  # This will be the original query for the task
        ]

        # Add candidate responses for evaluation
        for role, response_data in candidate_responses:
            message = response_data["message"]
            candidate_content = message.get("content")
            candidate_tool_calls = message.get("tool_calls")

            if candidate_content and candidate_tool_calls:
                # If both exist, prioritize content and append tool calls
                candidate_content += "\n\nTool Calls:\n" + json.dumps(candidate_tool_calls, indent=2)
            elif candidate_tool_calls:
                # If only tool calls exist, represent them as content
                candidate_content = "Tool Calls:\n" + json.dumps(candidate_tool_calls, indent=2)
            elif not candidate_content:
                # Ensure content is never None, even if empty
                candidate_content = ""

            reviewer_messages.append(
                {
                    "role": "assistant",
                    "content": f"--- Candidate Solution from {role} ({self.llm_clients[role].model}) ---\n{candidate_content}",
                    "tool_calls": candidate_tool_calls,  # Keep original tool calls separate if needed
                }
            )

        try:
            review_response, usage = await self.senior_reviewer_client.achat(
                messages=reviewer_messages,
                tools=[],  # Reviewer typically doesn't use tools for selection, but can be configured
            )
            choice_content = review_response["message"]["content"]
            self.event_publisher.publish(
                "tool_output",
                tool_name="senior_reviewer_selection",
                status="success",
                choice=choice_content[:200],
            )
        except Exception as e:
            self.logger.error(f"  Error getting response from Senior Reviewer: {e}")
            self.event_publisher.publish(
                "tool_output",
                tool_name="senior_reviewer_selection",
                status="error",
                message=str(e),
            )
            self.event_publisher.publish("tool_end", tool_name="senior_reviewer_selection")
            # Fallback to the first candidate if reviewer fails
            self.logger.warning("  Senior Reviewer failed. Falling back to the first candidate solution.")
            return candidate_responses[0][1], candidate_responses
        self.event_publisher.publish("tool_end", tool_name="senior_reviewer_selection")

        # Parse reviewer's choice - this needs to be robust
        chosen_response_data = self._parse_reviewer_choice(choice_content, candidate_responses)
        return chosen_response_data, candidate_responses

    def route_and_aggregate(
        self,
        messages: List[Dict],
        candidate_model_roles: List[str],
        tool_definitions: List[Dict],
        user_prompt_for_reviewer: str,  # A specific user prompt for the reviewer to evaluate
        task_description: str,  # Description of the task being performed
        options_override: Optional[Dict] = None,
    ) -> Tuple[Dict, List[Tuple[str, Dict]]]:
        """
        Routes the prompt to multiple candidate models, aggregates their responses,
        and uses a Senior Reviewer to pick the best or synthesize.

        Returns the chosen response and a list of all raw candidate responses.
        """
        candidate_responses: List[Tuple[str, Dict]] = []  # (model_role, raw_response_data)

        for role in candidate_model_roles:
            if role not in self.llm_clients:
                self.logger.warning(f"Model client for role '{role}' not found. Skipping.")
                continue

            client = self.llm_clients[role]
            self.logger.info(f"  Routing prompt to specialist model: {role} ({client.model})")
            self.event_publisher.publish("tool_start", tool_name="model_router", model=client.model, role=role)
            try:
                response_data, usage = client.chat(
                    messages=messages,
                    tools=tool_definitions,
                    options_override=options_override,
                )
                candidate_responses.append((role, response_data))
                self.event_publisher.publish(
                    "tool_output",
                    tool_name="model_router",
                    model=client.model,
                    role=role,
                    status="success",
                    content=response_data["message"].get("content", "")[:200],
                )
            except Exception as e:
                self.logger.error(f"  Error getting response from model {client.model} (role: {role}): {e}")
                self.event_publisher.publish(
                    "tool_output",
                    tool_name="model_router",
                    model=client.model,
                    role=role,
                    status="error",
                    message=str(e),
                )
            self.event_publisher.publish("tool_end", tool_name="model_router", model=client.model, role=role)

        if not candidate_responses:
            raise RuntimeError("No candidate models provided a response.")

        if len(candidate_responses) == 1:
            self.logger.info("  Only one candidate response. Skipping senior review.")
            return candidate_responses[0][1], candidate_responses

        self.logger.info("  Multiple candidate responses. Invoking Senior Reviewer to select the best.")
        self.event_publisher.publish(
            "tool_start",
            tool_name="senior_reviewer_selection",
            reviewer_model=self.senior_reviewer_client.model,
        )

        # Prepare messages for the Senior Reviewer
        reviewer_messages = [
            {"role": "system", "content": self._get_senior_reviewer_system_prompt()},
            {
                "role": "user",
                "content": user_prompt_for_reviewer,
            },  # This will be the original query for the task
        ]

        # Add candidate responses for evaluation
        for role, response_data in candidate_responses:
            message = response_data["message"]
            candidate_content = message.get("content")
            candidate_tool_calls = message.get("tool_calls")

            if candidate_content and candidate_tool_calls:
                # If both exist, prioritize content and append tool calls
                candidate_content += "\n\nTool Calls:\n" + json.dumps(candidate_tool_calls, indent=2)
            elif candidate_tool_calls:
                # If only tool calls exist, represent them as content
                candidate_content = "Tool Calls:\n" + json.dumps(candidate_tool_calls, indent=2)
            elif not candidate_content:
                # Ensure content is never None, even if empty
                candidate_content = ""

            reviewer_messages.append(
                {
                    "role": "assistant",
                    "content": f"--- Candidate Solution from {role} ({self.llm_clients[role].model}) ---\n{candidate_content}",
                    "tool_calls": candidate_tool_calls,  # Keep original tool calls separate if needed
                }
            )

        try:
            review_response, usage = self.senior_reviewer_client.chat(
                messages=reviewer_messages,
                tools=[],  # Reviewer typically doesn't use tools for selection, but can be configured
            )
            choice_content = review_response["message"]["content"]
            self.event_publisher.publish(
                "tool_output",
                tool_name="senior_reviewer_selection",
                status="success",
                choice=choice_content[:200],
            )
        except Exception as e:
            self.logger.error(f"  Error getting response from Senior Reviewer: {e}")
            self.event_publisher.publish(
                "tool_output",
                tool_name="senior_reviewer_selection",
                status="error",
                message=str(e),
            )
            self.event_publisher.publish("tool_end", tool_name="senior_reviewer_selection")
            # Fallback to the first candidate if reviewer fails
            self.logger.warning("  Senior Reviewer failed. Falling back to the first candidate solution.")
            return candidate_responses[0][1], candidate_responses
        self.event_publisher.publish("tool_end", tool_name="senior_reviewer_selection")

        # Parse reviewer's choice - this needs to be robust
        # For simplicity, let's assume the reviewer outputs the content of the chosen solution directly
        # or references the chosen model role/index.
        # A more complex implementation could have the reviewer output a tool call for selection.
        chosen_response_data = self._parse_reviewer_choice(choice_content, candidate_responses)
        return chosen_response_data, candidate_responses

    def _get_senior_reviewer_system_prompt(self) -> str:
        """System prompt for the Senior Reviewer for solution selection."""
        return (
            "You are a highly experienced Senior Reviewer. Your task is to evaluate multiple "
            "candidate solutions generated by specialist models for a given task. "
            "Your decision should be based on correctness, completeness, adherence to instructions, "
            "and overall quality. You should output the full content of the BEST solution. "
            "If the solutions include tool calls, output the full tool calls of the best option. "
            "If no solution is clearly superior or all are flawed, you may attempt to synthesize "
            "a better solution or indicate if further refinement is needed. "
            "Always prefer tool calls if the task requires actions. "
            "Your output must ONLY be the chosen solution's content or tool calls, or your synthesized version, nothing else."
        )

    def _parse_reviewer_choice(self, choice_content: str, candidate_responses: List[Tuple[str, Dict]]) -> Dict:
        """
        Parses the Senior Reviewer's output to select one of the candidate responses.
        Fallback to the first candidate if parsing fails.
        """
        # Attempt to match the choice content directly to one of the candidate responses
        for role, response_data in candidate_responses:
            if response_data["message"].get("content") == choice_content:
                self.logger.info(f"  Senior Reviewer explicitly chose solution from {role}.")
                return response_data
            if (
                response_data["message"].get("tool_calls")
                and json.dumps(response_data["message"]["tool_calls"]) == choice_content
            ):
                self.logger.info(f"  Senior Reviewer explicitly chose tool calls from {role}.")
                return response_data

        # If direct match fails, try to infer based on content similarity or keywords
        # This part can be made more sophisticated
        for role, response_data in candidate_responses:
            if role in choice_content.lower():  # Simple keyword match
                self.logger.info(f"  Senior Reviewer's choice content referenced {role}. Selecting it.")
                return response_data

        self.logger.warning(
            "  Could not definitively parse Senior Reviewer's choice. Falling back to the first candidate."
        )
        return candidate_responses[0][1]
