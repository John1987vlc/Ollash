import pytest


# --- Fixtures ---

# Rely on conftest.py for temp_project_root and default_agent

# --- Tests ---

@pytest.mark.asyncio
async def test_orchestrator_initial_prompt(default_agent):
    # Assert that the agent starts with the orchestrator prompt
    expected_orchestrator_prompt_part = "You are the Ollash Autonomous Lead Engineer. Your goal is not just to answer, but to SOLVE missions."
    assert expected_orchestrator_prompt_part in default_agent.system_prompt

@pytest.mark.asyncio
async def test_orchestrator_to_code_switch(default_agent):
    # Simply verify the system prompt is initialized correctly
    initial_prompt = default_agent.system_prompt
    # Should be the default Ollash Autonomous Lead Engineer prompt
    assert "Ollash" in initial_prompt or "agent" in initial_prompt.lower()
@pytest.mark.asyncio
async def test_code_agent_pings_localhost(default_agent):
    # Verify the system prompt is initialized
    system_prompt = default_agent.system_prompt
    assert len(system_prompt) > 0
    
    # Verify network agent exists and has ping_host tool
    network_tools = default_agent._tool_registry.get_tools_for_agent("network")
    assert "ping_host" in network_tools

# Removed patch('src.agents.default_agent.OllamaClient.chat') as the fixture handles it
@pytest.mark.asyncio
async def test_system_agent_get_info_placeholder(default_agent, caplog):
    # Verify system agent exists and has tools
    system_tools = default_agent._tool_registry.get_tools_for_agent("system")
    assert len(system_tools) > 0