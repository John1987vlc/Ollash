import pytest
from unittest.mock import MagicMock
from flask import Flask
from pathlib import Path

# Import blueprint and necessary enums
from frontend.blueprints.learning_bp import learning_bp, init_app
from backend.utils.core.preference_manager_extended import CommunicationStyle, ComplexityLevel


@pytest.fixture
def app():
    """Create a Flask app for testing learning endpoints."""
    app = Flask(__name__)
    app.config.update({"TESTING": True, "ollash_root_dir": Path("/tmp/ollash")})
    init_app(app)
    app.register_blueprint(learning_bp)
    return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def mock_managers(app):
    """
    Inject mocked managers into the app context to isolate blueprint routes.
    """
    mock_prefs = MagicMock()
    mock_patterns = MagicMock()
    mock_tuning = MagicMock()

    with app.app_context():
        app._learning_managers = {"preferences": mock_prefs, "patterns": mock_patterns, "tuning": mock_tuning}

    return {"preferences": mock_prefs, "patterns": mock_patterns, "tuning": mock_tuning}


class TestLearningBlueprint:
    """Test suite for Phase 3: Learning & Memory APIs."""

    # --- Preference Management Tests ---

    def test_get_preference_profile_success(self, client, mock_managers):
        # Mocking complex profile structure
        mock_profile = MagicMock()
        mock_profile.user_id = "user1"
        mock_profile.communication.style = CommunicationStyle.CONCISE
        mock_profile.communication.complexity = ComplexityLevel.EXPERT
        mock_profile.communication.interaction_prefs = []
        mock_profile.communication.use_examples = True
        mock_profile.communication.use_visuals = False
        mock_profile.total_interactions = 10
        mock_profile.positive_feedback_count = 8
        mock_profile.negative_feedback_count = 2
        mock_profile.learned_keywords = ["python"]
        mock_profile.frequently_used_commands = ["ls"]

        mock_managers["preferences"].get_profile.return_value = mock_profile

        response = client.get("/api/learning/preferences/profile/user1")

        assert response.status_code == 200
        data = response.get_json()["profile"]
        assert data["user_id"] == "user1"
        assert data["communication"]["style"] == "concise"
        assert data["communication"]["complexity"] == "expert"

    def test_update_preference_profile_success(self, client, mock_managers):
        mock_profile = MagicMock()
        mock_profile.communication.style = CommunicationStyle.DETAILED
        mock_profile.communication.complexity = ComplexityLevel.INTERMEDIATE
        mock_managers["preferences"].update_communication_style.return_value = mock_profile

        response = client.put(
            "/api/learning/preferences/profile/user1",
            json={"style": "detailed", "complexity": "intermediate", "use_examples": True},
        )

        assert response.status_code == 200
        assert response.get_json()["style"] == "detailed"
        mock_managers["preferences"].update_communication_style.assert_called_once()

    def test_update_preference_profile_invalid_enum(self, client):
        # Providing a value not in the CommunicationStyle enum
        response = client.put("/api/learning/preferences/profile/user1", json={"style": "invalid_style"})
        assert response.status_code == 400
        assert "Invalid value" in response.get_json()["message"]

    # --- Pattern Analysis Tests ---

    def test_record_feedback_success(self, client, mock_managers):
        mock_entry = MagicMock()
        mock_entry.timestamp = "2026-02-21T12:00:00"
        mock_entry.score = 5
        mock_managers["patterns"].record_feedback.return_value = mock_entry

        response = client.post(
            "/api/learning/feedback/record", json={"user_id": "u1", "score": 5, "task_type": "code_gen"}
        )

        assert response.status_code == 200
        assert response.get_json()["entry_timestamp"] == mock_entry.timestamp
        # Verify it also triggered behavior tuning
        mock_managers["tuning"].adapt_to_feedback.assert_called_with(5, "code_gen", keywords=[])

    def test_get_detected_patterns_with_query_params(self, client, mock_managers):
        mock_pattern = MagicMock()
        mock_pattern.pattern_id = "p1"
        mock_pattern.pattern_type = "success"
        mock_pattern.description = "Stable output"
        mock_pattern.confidence = 0.9
        mock_pattern.frequency = 5
        mock_pattern.recommendations = []

        mock_managers["patterns"].get_patterns.return_value = [mock_pattern]

        response = client.get("/api/learning/patterns/detected?type=success&confidence=0.8&limit=5")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["patterns"]) == 1
        mock_managers["patterns"].get_patterns.assert_called_with(pattern_type="success", min_confidence=0.8, limit=5)

    # --- Behavior Tuning Tests ---

    def test_update_tuning_parameter_success(self, client, mock_managers):
        mock_managers["tuning"].update_parameter.return_value = True

        response = client.post("/api/learning/tuning/update", json={"parameter": "response_length", "new_value": 1500})

        assert response.status_code == 200
        assert response.get_json()["updated"] is True
        mock_managers["tuning"].update_parameter.assert_called_once()

    def test_reset_tuning_config(self, client, mock_managers):
        response = client.post("/api/learning/tuning/reset")
        assert response.status_code == 200
        mock_managers["tuning"].reset_to_defaults.assert_called_once()

    # --- Integrated Endpoints Tests ---

    def test_learning_health_check_healthy(self, client, mock_managers):
        # Mock paths to return True for exists()
        mock_managers["preferences"].prefs_dir.exists.return_value = True
        mock_managers["patterns"].data_dir.exists.return_value = True
        mock_managers["tuning"].tuning_dir.exists.return_value = True

        response = client.get("/api/learning/health-check")
        assert response.status_code == 200
        assert response.get_json()["status"] == "healthy"

    def test_get_learning_summary(self, client, mock_managers):
        # Mocking profile
        mock_profile = MagicMock()
        mock_profile.communication.style.value = "formal"
        mock_profile.communication.complexity.value = "intermediate"
        mock_profile.total_interactions = 5
        mock_managers["preferences"].get_profile.return_value = mock_profile

        # Mocking insights
        mock_managers["patterns"].get_insights.return_value = {"detected_patterns": 3}

        # Mocking tuning config
        mock_managers["tuning"].get_current_config.return_value = {"auto_tune_enabled": True}

        response = client.get("/api/learning/summary/user123")

        assert response.status_code == 200
        data = response.get_json()
        assert data["user_id"] == "user123"
        assert data["preferences"]["style"] == "formal"
        assert data["patterns"]["detected"] == 3
        assert data["tuning"]["auto_tune_enabled"] is True
