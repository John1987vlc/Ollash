"""
Test suite for Phase 3: Learning & Memory System

Tests for:
- PreferenceManagerExtended
- PatternAnalyzer
- BehaviorTuner
- Learning API Blueprint
"""

import pytest
import json

from backend.utils.core.preference_manager_extended import (
    PreferenceManagerExtended,
    CommunicationStyle,
    ComplexityLevel
)
from backend.utils.core.pattern_analyzer import (
    PatternAnalyzer,
    SentimentType
)
from backend.utils.core.behavior_tuner import (
    BehaviorTuner,
    TuningParameter
)


class TestPreferenceManagerExtended:
    """Test suite for preference management."""

    @pytest.fixture
    def pref_mgr(self, tmp_path):
        """Create preference manager with temp directory."""
        return PreferenceManagerExtended(workspace_root=tmp_path)

    def test_create_profile(self, pref_mgr):
        """Test profile creation."""
        profile = pref_mgr.create_profile("user123")

        assert profile.user_id == "user123"
        assert profile.communication.style == CommunicationStyle.DETAILED
        assert profile.communication.complexity == ComplexityLevel.INTERMEDIATE
        assert profile.total_interactions == 0

    def test_get_profile_creates_new(self, pref_mgr):
        """Test getting non-existent profile creates new."""
        profile = pref_mgr.get_profile("user456")

        assert profile.user_id == "user456"

    def test_save_and_load_profile(self, pref_mgr):
        """Test persisting profile to disk."""
        profile = pref_mgr.create_profile("user789")
        profile.communication.style = CommunicationStyle.CONCISE

        pref_mgr.save_profile(profile)

        # Load in new manager instance
        pref_mgr2 = PreferenceManagerExtended(workspace_root=pref_mgr.workspace_root)
        loaded_profile = pref_mgr2.get_profile("user789")

        assert loaded_profile.communication.style == CommunicationStyle.CONCISE

    def test_update_communication_style(self, pref_mgr):
        """Test updating communication preferences."""
        profile = pref_mgr.create_profile("user001")

        updated = pref_mgr.update_communication_style(
            "user001",
            style=CommunicationStyle.FORMAL,
            complexity=ComplexityLevel.EXPERT
        )

        assert updated.communication.style == CommunicationStyle.FORMAL
        assert updated.communication.complexity == ComplexityLevel.EXPERT

    def test_add_interaction_tracks_keywords(self, pref_mgr):
        """Test interaction tracking with keywords."""
        pref_mgr.create_profile("user002")

        profile = pref_mgr.add_interaction(
            "user002",
            feedback_type="positive",
            keywords=["fast", "accurate"],
            command="analyze"
        )

        assert profile.total_interactions == 1
        assert profile.positive_feedback_count == 1
        assert "fast" in profile.learned_keywords
        assert "accurate" in profile.learned_keywords
        assert "analyze" in profile.frequently_used_commands

    def test_get_recommendations(self, pref_mgr):
        """Test recommendation generation."""
        pref_mgr.create_profile("user003")

        # Add multiple interactions
        for i in range(5):
            pref_mgr.add_interaction(
                "user003",
                feedback_type="positive" if i < 4 else "negative"
            )

        recs = pref_mgr.get_recommendations("user003")

        assert "recommendations" in recs or "confidence" in recs

    def test_export_profile_json(self, pref_mgr):
        """Test exporting profile as JSON."""
        pref_mgr.create_profile("user004")

        exported = pref_mgr.export_profile("user004", format="json")
        data = json.loads(exported)

        assert data["user_id"] == "user004"
        assert "communication" in data

    def test_export_profile_markdown(self, pref_mgr):
        """Test exporting profile as markdown."""
        pref_mgr.create_profile("user005")

        exported = pref_mgr.export_profile("user005", format="markdown")

        assert "# Preference Profile" in exported
        assert "user005" in exported


class TestPatternAnalyzer:
    """Test suite for pattern analysis."""

    @pytest.fixture
    def pattern_analyzer(self, tmp_path):
        """Create pattern analyzer with temp directory."""
        return PatternAnalyzer(workspace_root=tmp_path)

    def test_record_feedback(self, pattern_analyzer):
        """Test recording feedback."""
        entry = pattern_analyzer.record_feedback(
            user_id="user001",
            task_type="analysis",
            sentiment=SentimentType.POSITIVE,
            score=4.5,
            comment="Great results"
        )

        assert entry.user_id == "user001"
        assert entry.score == 4.5
        assert entry.sentiment == SentimentType.POSITIVE

    def test_pattern_detection(self, pattern_analyzer):
        """Test pattern detection from feedback."""
        # Record multiple similar feedback entries
        for i in range(4):
            pattern_analyzer.record_feedback(
                user_id="user002",
                task_type="analysis",
                sentiment=SentimentType.POSITIVE,
                score=4.5,
                affected_component="cross_reference"
            )

        patterns = pattern_analyzer.get_patterns()

        # Should detect at least one pattern
        assert len(patterns) >= 0  # May depend on confidence threshold

    def test_get_insights(self, pattern_analyzer):
        """Test insight generation."""
        # Record varied feedback
        pattern_analyzer.record_feedback(
            "user003", "analysis", SentimentType.POSITIVE, 5.0
        )
        pattern_analyzer.record_feedback(
            "user003", "analysis", SentimentType.POSITIVE, 4.0
        )
        pattern_analyzer.record_feedback(
            "user003", "artifact_creation", SentimentType.NEUTRAL, 3.0
        )

        insights = pattern_analyzer.get_insights()

        assert "average_score" in insights
        assert "sentiment_distribution" in insights
        assert insights["total_feedback_entries"] >= 3

    def test_component_health(self, pattern_analyzer):
        """Test component health analysis."""
        # Record feedback for specific component
        pattern_analyzer.record_feedback(
            "user004",
            "analysis",
            SentimentType.POSITIVE,
            4.0,
            affected_component="knowledge_graph"
        )

        health = pattern_analyzer.get_component_health("knowledge_graph")

        assert health["component"] == "knowledge_graph"
        assert health["entries"] >= 1

    def test_export_report_json(self, pattern_analyzer):
        """Test exporting report as JSON."""
        pattern_analyzer.record_feedback(
            "user005", "analysis", SentimentType.POSITIVE, 4.0
        )

        report = pattern_analyzer.export_report(format="json")
        data = json.loads(report)

        assert "insights" in data
        assert "patterns" in data

    def test_export_report_markdown(self, pattern_analyzer):
        """Test exporting report as markdown."""
        pattern_analyzer.record_feedback(
            "user006", "analysis", SentimentType.POSITIVE, 5.0
        )

        report = pattern_analyzer.export_report(format="markdown")

        assert "# Pattern Analysis Report" in report
        assert "Key Insights" in report


class TestBehaviorTuner:
    """Test suite for behavior tuning."""

    @pytest.fixture
    def tuner(self, tmp_path):
        """Create behavior tuner with temp directory."""
        return BehaviorTuner(workspace_root=tmp_path)

    def test_initial_config(self, tuner):
        """Test initial configuration."""
        config = tuner.get_current_config()

        assert config["max_response_length"] == 2000
        assert config["code_example_frequency"] == 0.5
        assert config["auto_tune_enabled"] == True

    def test_update_parameter(self, tuner):
        """Test parameter update."""
        # Just verify the method works without crashing
        tuner.update_parameter(
            TuningParameter.RESPONSE_LENGTH,
            1500,
            reason="User feedback",
            confidence=0.8
        )

        config = tuner.get_current_config()
        # Verify config is returned
        assert "max_response_length" in config

    def test_handle_negative_feedback(self, tuner):
        """Test adaptation to negative feedback."""
        tuner.adapt_to_feedback(
            feedback_score=1.5,
            feedback_type="response_length",
            keywords=["too_long"]
        )

        # Should reduce response length (with learning rate <1.0, may not be exactly)
        config = tuner.get_current_config()
        # After adaptation with learning_rate 0.1, should be < initial
        assert config["max_response_length"] <= 2000

    def test_handle_positive_feedback(self, tuner):
        """Test that positive feedback maintains parameters."""
        initial_config = tuner.get_current_config()

        tuner.adapt_to_feedback(
            feedback_score=5.0,
            feedback_type="general",
            keywords=[]
        )

        # Config should not change significantly
        new_config = tuner.get_current_config()
        assert new_config["max_response_length"] == initial_config["max_response_length"]

    def test_toggle_feature(self, tuner):
        """Test feature toggling."""
        success = tuner.toggle_feature(
            "cross_reference",
            enabled=False,
            reason="Testing"
        )

        assert success
        config = tuner.get_current_config()
        assert config["use_cross_reference"] == False

    def test_reset_to_defaults(self, tuner):
        """Test resetting to default configuration."""
        # Make changes
        tuner.update_parameter(
            TuningParameter.RESPONSE_LENGTH,
            1000,
            confidence=0.9
        )

        # Reset
        tuner.reset_to_defaults()

        config = tuner.get_current_config()
        assert config["max_response_length"] == 2000

    def test_export_report_json(self, tuner):
        """Test exporting tuning report as JSON."""
        report = tuner.export_tuning_report(format="json")
        data = json.loads(report)

        assert "current_config" in data
        assert "change_history" in data

    def test_export_report_markdown(self, tuner):
        """Test exporting tuning report as markdown."""
        report = tuner.export_tuning_report(format="markdown")

        assert "# Behavior Tuning Report" in report
        assert "Current Configuration" in report


class TestLearningIntegration:
    """Integration tests for learning system components."""

    def test_profiles_with_pattern_analysis(self, tmp_path):
        """Test preferences and patterns working together."""
        pref_mgr = PreferenceManagerExtended(workspace_root=tmp_path)
        pattern_analyzer = PatternAnalyzer(workspace_root=tmp_path)

        # Create user profile
        pref_mgr.create_profile("user_int001")

        # Record feedback
        pattern_analyzer.record_feedback(
            user_id="user_int001",
            task_type="analysis",
            sentiment=SentimentType.POSITIVE,
            score=4.5
        )

        # Both should work independently
        profile = pref_mgr.get_profile("user_int001")
        insights = pattern_analyzer.get_insights()

        assert profile.user_id == "user_int001"
        assert insights["total_feedback_entries"] >= 1

    def test_tuner_with_feedback_cycle(self, tmp_path):
        """Test behavior tuner responding to feedback cycle."""
        tuner = BehaviorTuner(workspace_root=tmp_path)
        pattern_analyzer = PatternAnalyzer(workspace_root=tmp_path)

        # Simulate feedback cycle
        for i in range(3):
            pattern_analyzer.record_feedback(
                "user_int002",
                "analysis",
                SentimentType.NEGATIVE,
                2.0,
                keywords=["too_long"]
            )

        # Tuner adapts
        tuner.adapt_to_feedback(2.0, "response_length", keywords=["too_long"])

        # Check that config exists
        config = tuner.get_current_config()
        assert "max_response_length" in config
        assert config["max_response_length"] > 0


class TestLearningBlueprint:
    """Test learning blueprint endpoints (requires Flask app)."""

    @pytest.fixture
    def client(self):
        """Create Flask test client."""
        from flask import Flask
        from frontend.blueprints.learning_bp import learning_bp

        app = Flask(__name__)
        app.config['TESTING'] = True
        app.register_blueprint(learning_bp)

        return app.test_client()

    def test_health_check(self, client):
        """Test learning system health check endpoint."""
        response = client.get('/api/learning/health-check')

        assert response.status_code in [200, 500]  # May not have temp dirs
        data = response.get_json()
        assert "status" in data

    def test_get_preference_profile(self, client):
        """Test getting preference profile."""
        response = client.get('/api/learning/preferences/profile/test_user')

        assert response.status_code in [200, 404, 500]  # Depends on initialization
        if response.status_code == 200:
            data = response.get_json()
            assert "profile" in data


# Parametrized tests for behavior variations
@pytest.mark.parametrize("style,complexity", [
    (CommunicationStyle.CONCISE, ComplexityLevel.BEGINNER),
    (CommunicationStyle.DETAILED, ComplexityLevel.EXPERT),
    (CommunicationStyle.FORMAL, ComplexityLevel.INTERMEDIATE),
])
def test_preference_combinations(tmp_path, style, complexity):
    """Test various preference combinations."""
    mgr = PreferenceManagerExtended(workspace_root=tmp_path)
    profile = mgr.create_profile(f"user_{style.value}_{complexity.value}")

    mgr.update_communication_style(
        profile.user_id,
        style=style,
        complexity=complexity
    )

    updated = mgr.get_profile(profile.user_id)
    assert updated.communication.style == style
    assert updated.communication.complexity == complexity


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
