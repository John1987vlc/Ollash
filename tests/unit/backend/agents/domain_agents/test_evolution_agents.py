"""
Unit tests for Evolution Agents.
"""
import pytest
from unittest.mock import MagicMock
from backend.agents.domain_agents.evolution_agents import (
    UXDesignerAgent,
    SecurityAgent,
    PerformanceAgent,
    ProductManagerAgent,
    TesterAgent as EvoTesterAgent,
    VisualReviewAgent,
)

@pytest.fixture
def mock_llm_client_manager():
    manager = MagicMock()
    manager.get_client.return_value = MagicMock()
    return manager

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.get.return_value = "mock_model"
    return config

@pytest.fixture
def mock_logger():
    return MagicMock()

def test_ux_designer_agent(mock_llm_client_manager, mock_config, mock_logger):
    # Setup mock LLM response
    mock_client = mock_llm_client_manager.get_client.return_value
    mock_client.chat.return_value = ({"content": "Add flexbox and change background to dark gray."}, {})

    agent = UXDesignerAgent(
        llm_client_manager=mock_llm_client_manager,
        config=mock_config,
        logger=mock_logger
    )
    result = agent.run({"index.html": "<html></html>"})
    assert result["status"] == "success"
    assert "flexbox" in result["feedback"]

def test_security_agent(mock_llm_client_manager, mock_config, mock_logger):
    mock_client = mock_llm_client_manager.get_client.return_value
    mock_client.chat.return_value = ({"content": "Found SQL injection vulnerability."}, {})

    agent = SecurityAgent(
        llm_client_manager=mock_llm_client_manager,
        config=mock_config,
        logger=mock_logger
    )
    result = agent.run({"main.py": "query = f'SELECT * FROM users WHERE id={user_id}'"})
    assert result["status"] == "success"
    assert "SQL injection" in result["feedback"]

def test_product_manager_agent(mock_llm_client_manager, mock_config, mock_logger):
    mock_client = mock_llm_client_manager.get_client.return_value
    mock_client.chat.return_value = ({"content": "Add a user profile dashboard."}, {})

    agent = ProductManagerAgent(
        llm_client_manager=mock_llm_client_manager,
        config=mock_config,
        logger=mock_logger
    )
    result = agent.run({"app.js": "console.log('App started')"}, "A simple app")
    assert result["status"] == "success"
    assert "dashboard" in result["epic"]

def test_visual_review_agent_no_index(mock_llm_client_manager, mock_config, mock_logger):
    """Test that VisualReviewAgent safely skips if index.html is missing."""
    agent = VisualReviewAgent(
        llm_client_manager=mock_llm_client_manager,
        config=mock_config,
        logger=mock_logger
    )
    result = agent.run({"main.js": "console.log('no index html');"}, "/fake/path")
    assert result["status"] == "skipped"
    assert "No index.html found" in result["reason"]
