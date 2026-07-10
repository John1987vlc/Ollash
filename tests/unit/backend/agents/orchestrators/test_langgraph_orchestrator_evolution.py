"""
Unit tests for LangGraph Swarm Orchestrator with Evolution nodes.
"""
import pytest
from unittest.mock import MagicMock
from pathlib import Path
from backend.agents.orchestrators.langgraph_orchestrator import LangGraphSwarmOrchestrator

def test_langgraph_orchestrator_initialization_with_evolution():
    """Test that the orchestrator initializes without errors and compiles the graph with new nodes."""
    
    mock_architect = MagicMock()
    mock_developer = MagicMock()
    mock_devops = MagicMock()
    mock_auditor = MagicMock()
    mock_tester = MagicMock()
    mock_ux = MagicMock()
    mock_security = MagicMock()
    mock_performance = MagicMock()
    mock_pm = MagicMock()
    mock_visual = MagicMock()
    mock_blackboard = MagicMock()
    mock_logger = MagicMock()
    
    # Initialization should compile the graph
    orchestrator = LangGraphSwarmOrchestrator(
        architect_agent=mock_architect,
        developer_agent=mock_developer,
        devops_agent=mock_devops,
        auditor_agent=mock_auditor,
        blackboard=mock_blackboard,
        logger=mock_logger,
        generated_projects_dir=Path(".test_gen"),
        tester_agent=mock_tester,
        ux_designer_agent=mock_ux,
        security_agent=mock_security,
        performance_agent=mock_performance,
        product_manager_agent=mock_pm,
        visual_review_agent=mock_visual
    )
    
    assert orchestrator._tester is mock_tester
    assert orchestrator._ux_designer is mock_ux
    assert orchestrator._visual_reviewer is mock_visual
    assert orchestrator._security is mock_security
    assert orchestrator._performance is mock_performance
    assert orchestrator._product_manager is mock_pm
    
    # We can inspect the internal graph loosely
    # It shouldn't have crashed during `_build_graph`
    assert orchestrator._graph is not None

