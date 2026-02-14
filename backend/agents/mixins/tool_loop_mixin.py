from abc import ABC
from typing import Dict, Any, Optional, List
import asyncio

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.loop_detector import LoopDetector
from backend.utils.core.event_publisher import EventPublisher
from backend.utils.core.confirmation_manager import ConfirmationManager # Assuming this handles confirmation gates
from backend.utils.core.permission_profiles import PolicyEnforcer # For tool confirmation policies
from backend.interfaces.itool_executor import IToolExecutor
from backend.utils.core.tool_span_manager import ToolSpanManager # NEW


class ToolLoopMixin(ABC):
    """
    Mixin for managing the execution loop of tools and detecting infinite loops.
    Assumes the inheriting class provides:
    - self.logger (AgentLogger)
    - self.tool_executor (IToolExecutor)
    - self.loop_detector (LoopDetector)
    - self.event_publisher (EventPublisher)
    - self.policy_enforcer (PolicyEnforcer) for confirmation gates
    - self.confirmation_manager (ConfirmationManager)
    - self.tool_span_manager (ToolSpanManager) # NEW
    """

    async def _execute_tool_loop(self, tool_calls: List[Dict], user_input: str) -> List[Dict]:
        """
        Executes a series of tool calls in a loop, handling confirmation gates, loop detection,
        and recording execution spans.

        Args:
            tool_calls: A list of dictionaries, each representing a tool call.
            user_input: The original user input that triggered the tool calls, for context.

        Returns:
            A list of tool outputs (dictionaries).
        """
        tool_outputs = []
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = tool_call["function"]["arguments"]
            
            tool_call_id = self.tool_span_manager.start_span(tool_name, tool_args, tool_call.get("id")) # NEW: Start span

            self.logger.info(f"Agent attempting to use tool: {tool_name} with args: {tool_args}")
            self.event_publisher.publish("tool_code", {"tool_name": tool_name, "tool_args": tool_args})

            # Policy Enforcement & Confirmation Gate
            authorized, reason = self.policy_enforcer.authorize_tool_execution(tool_name, resource_path=tool_args.get("path", tool_args.get("file_path", tool_args.get("command", ""))), context=tool_args)

            if not authorized:
                self.logger.warning(f"Tool '{tool_name}' execution denied by policy: {reason}")
                result_output = {
                    "tool_call_id": tool_call_id,
                    "output": f"Tool '{tool_name}' execution denied by policy: {reason}"
                }
                tool_outputs.append(result_output)
                self.tool_span_manager.end_span(tool_call_id, success=False, result=result_output, error=f"Policy denied: {reason}")
                continue # Skip execution of this tool call

            # If authorized by policy, check for user confirmation if auto-approve is not enabled
            if self.policy_enforcer.is_tool_state_modifying(tool_name) and not self.policy_enforcer.is_auto_approve_enabled():
                confirmed = await self.confirmation_manager.request_confirmation(
                    f"Confirm execution of state-modifying tool '{tool_name}' with args: {tool_args}?"
                )
                if not confirmed:
                    self.logger.warning(f"Tool '{tool_name}' execution denied by user.")
                    result_output = {
                        "tool_call_id": tool_call_id,
                        "output": f"Tool '{tool_name}' execution denied by user."
                    }
                    tool_outputs.append(result_output)
                    self.tool_span_manager.end_span(tool_call_id, success=False, result=result_output, error="Execution denied by user")
                    continue # Skip execution of this tool call

            success = False
            result_output: Any = {}
            error_message: Optional[str] = None
            tool_execution_output: Any = None # Store the actual output from tool_executor

            try:
                # Execute the tool using the injected tool_executor
                tool_execution_output = await self.tool_executor.execute_tool(tool_name, **tool_args)
                self.logger.info(f"Tool '{tool_name}' executed. Output: {tool_execution_output}")
                result_output = {
                    "tool_call_id": tool_call_id,
                    "output": tool_execution_output
                }
                tool_outputs.append(result_output)
                self.event_publisher.publish("tool_output", {"tool_name": tool_name, "output": tool_execution_output})
                success = True
            except Exception as e:
                error_message = f"Error executing tool '{tool_name}': {e}"
                self.logger.error(error_message, exception=e)
                result_output = {
                    "tool_call_id": tool_call_id,
                    "output": f"Error executing tool '{tool_name}': {e}"
                }
                tool_outputs.append(result_output)
                self.event_publisher.publish("tool_error", {"tool_name": tool_name, "error": str(e)})
            finally:
                self.tool_span_manager.end_span(tool_call_id, success=success, result=result_output, error=error_message)

            # After tool execution and recording, check for loops
            self.loop_detector.record_action(tool_name, tool_args, tool_execution_output if success else error_message)
            if self.loop_detector.detect_loop():
                self.logger.warning(f"Loop detected after tool: {tool_name}, args: {tool_args}. Aborting further tool execution.")
                tool_outputs[-1]["output"] += "\nLoop detected. Aborting further tool execution." # Append to last output
                break # Exit the tool loop
        return tool_outputs
