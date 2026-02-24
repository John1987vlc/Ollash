import pytest
from backend.agents.default_agent import DefaultAgent

@pytest.mark.manual
class TestAgentUseCases:
    """
    Manual E2E tests for common IT Agent use cases.
    These tests require a running Ollama instance.
    Run with: pytest tests/manual/test_use_cases.py -m manual -s
    """

    def setup_method(self):
        # We use a real agent instance
        self.agent = DefaultAgent(
            project_root=".",
            auto_confirm=True, # Auto-confirm for tests to run without interaction
        )
        self.captured_tools = []

        # Subscribe to capture which tools are being called via the agent's publisher
        self.agent.event_publisher.subscribe("tool_start", lambda ev, data: self.captured_tools.append(data['tool_name']))

    @pytest.mark.asyncio
    @pytest.mark.parametrize("instruction,expected_tools", [
        ("dime mi ip", ["run_shell_command", "get_system_info"]),
        ("dime mi mac address", ["run_shell_command", "get_system_info"]),
        ("dime mi sistema operativo", ["get_system_info"]),
        ("listame los archivos de esta carpeta", ["list_directory", "run_shell_command"]),
        ("que procesos consumen mas ram", ["list_processes", "run_shell_command"])
    ])
    async def test_it_agent_flow(self, instruction, expected_tools):
        """Generic test runner for multiple instructions."""
        self.captured_tools = []
        print(f"\n[USER]: {instruction}")

        # Execute chat
        res = await self.agent.chat(instruction)

        # Display output
        text = res['text'] if isinstance(res, dict) else str(res)
        print(f"[AGENT]: {text}")
        print(f"[TOOLS]: {self.captured_tools}")

        # Check if the agent used its technical capabilities
        used_technical_tool = any(t in self.captured_tools for t in expected_tools)
        assert used_technical_tool, f"Agent failed to use any of the expected tools: {expected_tools}"

if __name__ == "__main__":
    # To run: pytest tests/manual/test_use_cases.py -m manual -s
    pass
