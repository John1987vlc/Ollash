"""Tests for the centralized configuration system."""
import pytest
import importlib
import json
from backend.core import config as agent_config

def test_config_loads_from_env(monkeypatch):
    """
    Tests that the config object correctly loads values from environment variables,
    and that the override mechanism works.
    """
    # 1. Define test-specific values
    test_url = "http://test-ollama:1234"
    test_model = "test-model-from-env"
    tool_settings = {"max_iterations": 99, "auto_confirm_tools": True}

    # 2. Set environment variables using monkeypatch
    monkeypatch.setenv("OLLAMA_URL", test_url)
    monkeypatch.setenv("DEFAULT_MODEL", test_model)
    monkeypatch.setenv("TOOL_SETTINGS_JSON", json.dumps(tool_settings))

    # 3. Force a reload of the config module to pick up the patched environment
    importlib.reload(agent_config)
    
    # 4. The imported `config` object should now have the new values
    assert agent_config.config.OLLAMA_URL == test_url
    assert agent_config.config.DEFAULT_MODEL == test_model
    assert agent_config.config.TOOL_SETTINGS is not None
    assert agent_config.config.TOOL_SETTINGS["max_iterations"] == 99
    assert agent_config.config.TOOL_SETTINGS["auto_confirm_tools"] is True

def test_legacy_ollama_url_override(monkeypatch):
    """
    Tests that 'ollama_url' within LLM_MODELS_JSON correctly overrides
    the base OLLAMA_URL environment variable for legacy compatibility.
    """
    base_url = "http://base-url:11434"
    legacy_url = "http://legacy-url-from-json:11434"
    
    models_config = {
        "ollama_url": legacy_url,
        "default_model": "some-model",
        "models": {
            "coder": "coder-model"
        }
    }

    monkeypatch.setenv("OLLAMA_URL", base_url)
    monkeypatch.setenv("LLM_MODELS_JSON", json.dumps(models_config))

    # Reload config to apply patched env vars
    importlib.reload(agent_config)

    # The legacy 'ollama_url' from the JSON should take precedence
    assert agent_config.config.OLLAMA_URL == legacy_url
