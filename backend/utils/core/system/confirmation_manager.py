import asyncio
import uuid
import datetime
from typing import Any, Dict, List

from colorama import Fore, Style

from backend.core.config_schemas import ToolSettingsConfig


class ConfirmationManager:
    """Manages confirmation gates for state-modifying tools."""

    MODIFY_ACTIONS = {"write_file", "delete_file", "git_commit", "git_push", "run_shell_command", "replace"}

    def __init__(
        self,
        logger: Any,
        config: ToolSettingsConfig,
        auto_confirm: bool = False,
        tool_registry: Any = None,
        event_publisher: Any = None,
    ):
        self.logger = logger
        self.config = config
        self.auto_confirm = auto_confirm
        self.tool_registry = tool_registry
        self.event_publisher = event_publisher

        self.git_auto_confirm_lines_threshold: int = self.config.git_auto_confirm_lines_threshold
        self.auto_confirm_minor_git_commits: bool = self.config.auto_confirm_minor_git_commits

        self.write_auto_confirm_lines_threshold: int = self.config.write_auto_confirm_lines_threshold
        self.auto_confirm_minor_writes: bool = self.config.auto_confirm_minor_writes

        self.critical_paths_patterns: List[str] = self.config.critical_paths_patterns

        # HIL state
        self._pending_responses: Dict[str, asyncio.Event] = {}
        self._responses_data: Dict[str, Dict] = {}

    def get_tool_definitions(self, active_tool_names: List[str]) -> List[Dict]:
        """
        Retrieves the tool definitions for the currently active tools from the ToolRegistry.
        """
        if self.tool_registry is None:
            raise ValueError("ToolRegistry not set in ToolConfirmationManager.")
        return self.tool_registry.get_tool_definitions(active_tool_names)

    def _requires_confirmation(self, tool_name: str) -> bool:
        """Check if a tool requires user confirmation"""
        return tool_name in self.MODIFY_ACTIONS

    async def request_confirmation(self, action: str, details: Dict) -> bool:
        """Asks user for confirmation, supporting both CLI and Web HIL."""
        if self.auto_confirm:
            self.logger.info(f"Auto-confirming action: {action}")
            return True

        # Generate a unique request ID
        req_id = str(uuid.uuid4())[:8]

        # 1. Prepare for response BEFORE publishing request to avoid race conditions
        event = asyncio.Event()
        if self.event_publisher:
            self._pending_responses[req_id] = event

            def on_hil_response(event_type, event_data):
                data = event_data  # The publisher passes event_type and event_data
                if data.get("request_id") == req_id:
                    self._responses_data[req_id] = data
                    event.set()

            self.event_publisher.subscribe("hil_response", on_hil_response)

        # 2. Notify via EventPublisher for Web UI/CLI
        if self.event_publisher:
            hil_data = {
                "id": req_id,
                "type": action,
                "title": f"Confirm Action: {action}",
                "details": details,
                "timestamp": datetime.datetime.now().isoformat(),
                "agent": "DefaultAgent",
            }
            self.event_publisher.publish("hil_request", hil_data)
            self.logger.info(f"HIL Request sent to UI/CLI: {req_id}")

        # 3. Log to console (always, for visibility)
        self._log_confirmation_details(action, details)

        # 4. Wait for response
        if self.event_publisher:
            try:
                # Wait with timeout (e.g. 5 minutes)
                await asyncio.wait_for(event.wait(), timeout=300)
                response_data = self._responses_data.get(req_id, {})
                approved = response_data.get("response") == "approve"

                if approved:
                    self.logger.info(f"✅ Action {action} APPROVED by user.")
                else:
                    self.logger.warning(f"❌ Action {action} REJECTED by user.")

                return approved
            except asyncio.TimeoutError:
                self.logger.error(f"⌛ HIL Request {req_id} timed out.")
                return False
            finally:
                # Cleanup
                self._pending_responses.pop(req_id, None)
                self._responses_data.pop(req_id, None)
                self.event_publisher.unsubscribe("hil_response", on_hil_response)
        else:
            # Fallback to blocking CLI input if no event publisher
            return self._ask_blocking_input(action, details)

    def _log_confirmation_details(self, action: str, details: Dict):
        """Helper to log pretty confirmation details to console."""
        self.logger.info(f"\n{Fore.YELLOW}{'=' * 60}")
        self.logger.info(f"⚠️  CONFIRMATION REQUIRED: {action}")
        self.logger.info(f"{'=' * 60}{Style.RESET_ALL}")

        if action == "write_file" or action == "replace":
            path = details.get("path") or details.get("file_path", "N/A")
            self.logger.info(f"📝 File: {Fore.CYAN}{path}{Style.RESET_ALL}")
            if "content" in details:
                self.logger.info(f"📏 Size: {len(str(details['content']))} characters")

        elif action in ["run_shell_command", "run_command", "execute_script"]:
            cmd = details.get("command") or details.get("filename", "N/A")
            self.logger.info(f"💻 Action: {Fore.RED}{cmd}{Style.RESET_ALL}")
            if "args" in details:
                self.logger.info(f"🔢 Args: {details['args']}")

        self.logger.info(f"{Fore.YELLOW}{'=' * 60}{Style.RESET_ALL}")

    def _ask_blocking_input(self, action: str, details: Dict) -> bool:
        """Classic blocking input for CLI mode."""
        print(f"\n{Fore.YELLOW}🤔 [Confirmation Required]{Style.RESET_ALL}")
        while True:
            response = input(f"{Fore.GREEN}Proceed with {action}? (y/n/cancel): {Style.RESET_ALL}").strip().lower()
            if response in ["yes", "y", "si", "s"]:
                return True
            elif response in ["no", "n"]:
                return False
            elif response in ["c", "cancel"]:
                self.logger.warning("Operation cancelled by user.")
                return False
