import pytest

@pytest.mark.unit
def test_agent_initialization(default_agent):
    """Test that the agent initializes correctly."""
    assert default_agent is not None
    assert default_agent.llm_manager is not None
    assert default_agent.project_root is not None
    assert default_agent.logger is not None

@pytest.mark.unit
def test_agent_core_services(default_agent):
    """Test that core services are available."""
    assert default_agent.file_manager is not None
    assert default_agent.tool_executor is not None
    assert default_agent.documentation_manager is not None
    assert default_agent.learning_system is not None

@pytest.mark.unit
def test_agent_tools_availability(default_agent):
    """Test that specialized tools are available across domains."""
    registry = default_agent._tool_registry
    assert registry is not None

    domains = ["orchestrator", "code", "network", "system", "cybersecurity"]
    for domain in domains:
        tools = registry.get_tools_for_agent(domain)
        assert len(tools) > 0, f"Domain {domain} should have tools"

@pytest.mark.unit
def test_agent_active_configuration(default_agent):
    """Test that the agent has active tools and prompt."""
    assert len(default_agent.active_tool_names) > 0
    assert default_agent.system_prompt is not None
    assert len(default_agent.system_prompt) > 0
