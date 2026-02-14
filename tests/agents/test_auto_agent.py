"""Tests for AutoAgent pipeline phases."""
import json
import pytest
from pathlib import Path
from backend.core.kernel import AgentKernel
from backend.agents.auto_agent import AutoAgent

@pytest.fixture
def test_kernel(monkeypatch, tmp_path):
    """
    Provides a clean AgentKernel instance with a controlled configuration
    for testing AutoAgent.
    """
    # 1. Define test-specific values
    test_url = "http://custom:11434"
    models_config = {
        "models": {
            "prototyper": "test-proto",
            "coder": "test-coder",
        }
    }

    # 2. Monkeypatch environment variables
    monkeypatch.setenv("OLLAMA_URL", test_url)
    monkeypatch.setenv("LLM_MODELS_JSON", json.dumps(models_config))
    monkeypatch.setenv("USE_BENCHMARK_SELECTOR", "False")
    monkeypatch.setenv("AGENT_FEATURES_JSON", json.dumps({"enable_auto_learning": False}))
    
    # 3. Force reload of config and create kernel
    from backend.core.config import reload_config
    reload_config()
    
    (tmp_path / "logs").mkdir() # Ensure logs dir exists
    kernel = AgentKernel(ollash_root_dir=tmp_path)
    return kernel

class TestAutoAgentInitialization:
    """Tests for AutoAgent initialization and configuration using an injected kernel."""

    def test_init_creates_llm_clients(self, test_kernel):
        """
        Tests that the AutoAgent, when given a pre-configured kernel,
        initializes its LLM clients correctly.
        """
        agent = AutoAgent(kernel=test_kernel)
        
        assert "prototyper" in agent.llm_manager.llm_clients
        assert agent.llm_manager.llm_clients["prototyper"] is not None
        assert agent.llm_manager.llm_clients["prototyper"].model == "test-proto"
        assert "coder" in agent.llm_manager.llm_clients
        
    def test_init_uses_env_var_url(self, test_kernel):
        """
        Tests that the kernel's config reflects the monkeypatched environment
        variable for OLLAMA_URL.
        """
        agent = AutoAgent(kernel=test_kernel)
        config = agent.kernel.get_llm_models_config()
        assert config.ollama_url == "http://custom:11434"
