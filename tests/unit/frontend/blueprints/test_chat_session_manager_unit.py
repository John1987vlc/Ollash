"""Unit tests for src/web/services/chat_session_manager.py."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestChatSessionManager:
    def test_create_session(self, tmp_path):
        # Need config for DefaultAgent
        config_dir = tmp_path / "config"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "settings.json").write_text(
            json.dumps(
                {
                    "model": "test",
                    "ollama_url": "http://localhost:11434",
                    "timeout": 30,
                    "max_tokens": 1024,
                    "temperature": 0.5,
                    "history_limit": 10,
                    "sandbox": "limited",
                    "project_root": ".",
                    "default_system_prompt_path": "prompts/orchestrator/default_orchestrator.json",
                    "models": {
                        "default": "test",
                        "coding": "test",
                        "reasoning": "test",
                        "orchestration": "test",
                        "summarization": "test",
                        "self_correction": "test",
                        "embedding": "test",
                    },
                }
            )
        )
        prompts_dir = tmp_path / "prompts" / "orchestrator"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        (prompts_dir / "default_orchestrator.json").write_text(json.dumps({"system_prompt": "test", "tools": []}))
        for domain in ["code", "network", "system", "cybersecurity"]:
            d = tmp_path / "prompts" / domain
            d.mkdir(parents=True, exist_ok=True)
            fname = "default_agent.json" if domain == "code" else f"default_{domain}_agent.json"
            (d / fname).write_text(json.dumps({"system_prompt": "test", "tools": []}))

        with patch("frontend.services.chat_session_manager.DefaultAgent"):
            from backend.utils.core.system.event_publisher import EventPublisher
            from frontend.services.chat_session_manager import ChatSessionManager

            publisher = EventPublisher()
            mgr = ChatSessionManager(tmp_path, event_publisher=publisher)
            session_id = mgr.create_session()
            assert session_id is not None
            assert mgr.get_session(session_id) is not None

    def test_max_sessions_limit(self):
        with patch("frontend.services.chat_session_manager.DefaultAgent"):
            from backend.utils.core.system.event_publisher import EventPublisher
            from frontend.services.chat_session_manager import ChatSessionManager

            publisher = EventPublisher()
            mgr = ChatSessionManager(Path("."), event_publisher=publisher)
            for _ in range(5):
                mgr.create_session()
            with pytest.raises(RuntimeError, match="Maximum"):
                mgr.create_session()

    def test_agent_type_sets_active_type(self):
        with patch("frontend.services.chat_session_manager.DefaultAgent") as MockAgent:
            mock_instance = MockAgent.return_value
            mock_instance._agent_tool_name_mappings = {
                "code": ["read_file", "write_file"],
                "orchestrator": ["plan_actions"],
            }
            mock_instance.active_agent_type = "orchestrator"
            mock_instance.active_tool_names = ["plan_actions"]

            from backend.utils.core.system.event_publisher import EventPublisher
            from frontend.services.chat_session_manager import ChatSessionManager

            publisher = EventPublisher()
            mgr = ChatSessionManager(Path("."), event_publisher=publisher)
            mgr.create_session(agent_type="code")

            # Should have set agent type on the mock
            assert mock_instance.active_agent_type == "code"
            assert mock_instance.active_tool_names == ["read_file", "write_file"]
