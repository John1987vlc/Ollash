"""Network discovery tests - simplified version"""

import pytest

# The fixtures mock_ollama_client, temp_project_root, and default_agent are provided by conftest.py


@pytest.mark.asyncio
async def test_network_discovery_initialization(default_agent):
    """Test that network tools are available"""
    tools = default_agent._tool_registry.get_tools_for_agent("network")
    assert len(tools) > 0


@pytest.mark.asyncio
async def test_network_agent_has_ping_tool(default_agent):
    """Test that network agent has ping tool"""
    tools = default_agent._tool_registry.get_tools_for_agent("network")
    assert "ping_host" in tools
