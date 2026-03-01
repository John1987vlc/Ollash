from abc import ABC
from typing import Any, Dict, List, Optional


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
    - self.tool_span_manager (ToolSpanManager)
    """

    async def _execute_tool_loop(self, tool_calls: List[Dict], user_input: str) -> List[Dict]:
        """
        Executes a series of tool calls in a loop, handling confirmation gates, loop detection,
        and recording execution spans.
        """
        tool_outputs = []

        # F26: Track consecutive planning calls to prevent infinite planning loops
        if not hasattr(self, "_consecutive_planning_count"):
            self._consecutive_planning_count = 0

        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            tool_args = tool_call["function"]["arguments"]

            # Create a signature for this call
            call_sig = f"{tool_name}:{str(tool_args)}"

            if self._failed_calls_tracker.get(call_sig, 0) > 2:
                self.logger.warning(
                    f"⚠️ Tool {tool_name} has failed multiple times with these args. Skipping to avoid infinite loop."
                )
                tool_outputs.append(
                    {
                        "tool_call_id": tool_call.get("id"),
                        "output": f"Error: This exact tool call has failed {self._failed_calls_tracker[call_sig]} times. Please try a different approach or ask for help.",
                        "ok": False,
                        "tool_name": tool_name,
                    }
                )
                continue

            # Update planning counter
            if tool_name in ["plan_actions", "analyze_project"]:
                self._consecutive_planning_count += 1
            else:
                self._consecutive_planning_count = 0

            if self._consecutive_planning_count > 3:
                self.logger.warning(f"⚠️ High repetition of {tool_name} detected. Forcing action phase.")
                # We return a fake error to the agent to force it to stop planning and start doing
                tool_outputs.append(
                    {
                        "tool_call_id": tool_call.get("id"),
                        "output": "Error: You have already planned multiple times. Do not plan again. Proceed IMMEDIATELY to implementation using write_file.",
                        "ok": False,
                        "tool_name": tool_name,
                    }
                )
                self._consecutive_planning_count = 0
                break

            tool_call_id = self.tool_span_manager.start_span(tool_name, tool_args, tool_call.get("id"))

            self.logger.info(f"Agent attempting to use tool: {tool_name} with args: {tool_args}")
            self.event_publisher.publish("tool_code", {"tool_name": tool_name, "tool_args": tool_args})

            # Policy Enforcement & Confirmation Gate
            authorized, reason = self.policy_enforcer.authorize_tool_execution(
                tool_name,
                resource_path=str(tool_args.get("path", tool_args.get("file_path", tool_args.get("command", "")))),
                context=tool_args,
            )

            if not authorized:
                self.logger.warning(f"Tool '{tool_name}' execution denied by policy: {reason}")
                result_output = {
                    "tool_call_id": tool_call_id,
                    "output": f"Tool '{tool_name}' execution denied by policy: {reason}. If you need this permission, explain why to the user.",
                    "ok": False,
                    "tool_name": tool_name,
                }
                tool_outputs.append(result_output)
                self.tool_span_manager.end_span(
                    tool_call_id,
                    success=False,
                    result=result_output,
                    error=f"Policy denied: {reason}",
                )
                continue

            # If authorized by policy, check for user confirmation if auto-approve is not enabled
            if (
                self.policy_enforcer.is_tool_state_modifying(tool_name)
                and not self.policy_enforcer.is_auto_approve_enabled()
            ):
                confirmed = await self.confirmation_manager.request_confirmation(action=tool_name, details=tool_args)
                if not confirmed:
                    self.logger.warning(f"Tool '{tool_name}' execution denied by user.")
                    result_output = {
                        "tool_call_id": tool_call_id,
                        "output": f"Tool '{tool_name}' execution denied by user.",
                        "ok": False,
                        "tool_name": tool_name,
                    }
                    tool_outputs.append(result_output)
                    self.tool_span_manager.end_span(
                        tool_call_id,
                        success=False,
                        result=result_output,
                        error="Execution denied by user",
                    )
                    continue

            success = False
            result_output: Any = {}
            error_message: Optional[str] = None
            tool_execution_output: Any = None

            try:
                self.logger.thinking(f"Executing {tool_name} to address: {user_input[:50]}...")

                # Execute the tool using the injected tool_executor
                tool_execution_output = await self.tool_executor.execute_tool(tool_name, **tool_args)

                self.logger.debug(f"DEBUG - Tool '{tool_name}' output: {tool_execution_output}")
                self.logger.info(f"✅ Tool '{tool_name}' executed successfully.")

                # If tool output indicates failure (e.g. {"ok": False}), track it
                is_ok = True
                if isinstance(tool_execution_output, dict):
                    is_ok = tool_execution_output.get("ok", True)

                if not is_ok:
                    self._failed_calls_tracker[call_sig] = self._failed_calls_tracker.get(call_sig, 0) + 1

                result_output = {
                    "tool_call_id": tool_call_id,
                    "output": tool_execution_output,
                    "ok": is_ok,
                    "tool_name": tool_name,
                }
                tool_outputs.append(result_output)
                self.event_publisher.publish(
                    "tool_output",
                    {"tool_name": tool_name, "output": tool_execution_output, "ok": is_ok},
                )
                success = is_ok
            except Exception as e:
                error_message = f"Error executing tool '{tool_name}': {str(e)}"
                import traceback

                self.logger.error(f"❌ {error_message}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")

                self._failed_calls_tracker[call_sig] = self._failed_calls_tracker.get(call_sig, 0) + 1

                friendly_error = f"Tool '{tool_name}' failed: {str(e)}"
                result_output = {
                    "tool_call_id": tool_call_id,
                    "output": f"Error: {friendly_error}",
                    "ok": False,
                    "tool_name": tool_name,
                }
                tool_outputs.append(result_output)

                if hasattr(self, "_event_bridge") and self._event_bridge:
                    self._event_bridge.push_event("error", {"message": friendly_error, "tool": tool_name})

                self.event_publisher.publish("tool_error", {"tool_name": tool_name, "error": str(e)})
            finally:
                self.tool_span_manager.end_span(
                    tool_call_id,
                    success=success,
                    result=result_output,
                    error=error_message,
                )

            # After tool execution and recording, check for loops
            self.loop_detector.record_action(
                tool_name,
                tool_args,
                tool_execution_output if success else error_message,
            )
            if self.loop_detector.detect_loop():
                self.logger.warning(
                    f"Loop detected after tool: {tool_name}, args: {tool_args}. Aborting further tool execution."
                )
                current_output = tool_outputs[-1].get("output", "")
                loop_msg = "\n[Loop detected. Aborting further tool execution. Please ask the user for guidance.]"

                if isinstance(current_output, str):
                    tool_outputs[-1]["output"] = current_output + loop_msg
                elif isinstance(current_output, dict):
                    tool_outputs[-1]["output"]["_loop_warning"] = loop_msg
                else:
                    tool_outputs[-1]["output"] = str(current_output) + loop_msg
                break
        return tool_outputs
