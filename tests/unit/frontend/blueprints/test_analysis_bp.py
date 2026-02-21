import pytest
from unittest.mock import MagicMock
from flask import Flask
from pathlib import Path

# Import blueprint and its routes
from frontend.blueprints.analysis_bp import analysis_bp, init_app


@pytest.fixture
def app():
    """Create a Flask app for testing analysis endpoints."""
    app = Flask(__name__)
    app.config.update({"TESTING": True, "ollash_root_dir": Path("/tmp/ollash"), "config": {}})
    init_app(app)
    app.register_blueprint(analysis_bp)
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
    mock_cross_ref = MagicMock()
    mock_kg = MagicMock()
    mock_decision = MagicMock()

    with app.app_context():
        app._analysis_managers = {
            "cross_ref": mock_cross_ref,
            "knowledge_graph": mock_kg,
            "decision_context": mock_decision,
        }

    return {"cross_ref": mock_cross_ref, "knowledge_graph": mock_kg, "decision_context": mock_decision}


class TestAnalysisBlueprint:
    """Test suite for advanced analysis endpoints."""

    # --- Cross-Reference Tests ---

    def test_compare_documents_success(self, client, mock_managers):
        mock_managers["cross_ref"].compare_documents.return_value = {"similarity": 0.85, "diff": []}

        response = client.post(
            "/api/analysis/cross-reference/compare", json={"doc1_path": "docs/doc1.md", "doc2_path": "docs/doc2.md"}
        )

        assert response.status_code == 200
        assert response.get_json()["similarity"] == 0.85
        mock_managers["cross_ref"].compare_documents.assert_called_once()

    def test_compare_documents_missing_payload(self, client):
        response = client.post(
            "/api/analysis/cross-reference/compare",
            json={
                "doc1_path": "docs/doc1.md"
                # Missing doc2_path
            },
        )
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_find_cross_references_success(self, client, mock_managers):
        mock_ref = MagicMock()
        mock_ref.to_dict.return_value = {"file": "test.py", "line": 10}
        mock_managers["cross_ref"].find_cross_references.return_value = [mock_ref]

        response = client.post("/api/analysis/cross-reference/find-references", json={"term": "API"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["count"] == 1
        assert data["references"][0]["line"] == 10

    # --- Knowledge Graph Tests ---

    def test_build_knowledge_graph_success(self, client, mock_managers):
        mock_managers["knowledge_graph"].build_from_documentation.return_value = {"nodes": 10, "edges": 15}

        response = client.post("/api/analysis/knowledge-graph/build", json={"doc_paths": ["docs/README.md"]})

        assert response.status_code == 200
        assert response.get_json()["stats"]["nodes"] == 10

    def test_find_knowledge_paths_success(self, client, mock_managers):
        mock_managers["knowledge_graph"].find_knowledge_paths.return_value = [["A", "B", "C"]]

        response = client.post("/api/analysis/knowledge-graph/paths", json={"start_term": "A", "end_term": "C"})

        assert response.status_code == 200
        data = response.get_json()
        assert data["path_count"] == 1
        assert data["paths"][0] == ["A", "B", "C"]

    def test_export_mermaid_diagram_success(self, client, mock_managers):
        mock_managers["knowledge_graph"].export_graph_mermaid.return_value = "graph TD; A-->B"

        response = client.get("/api/analysis/knowledge-graph/export/mermaid")

        assert response.status_code == 200
        assert "diagram" in response.get_json()
        assert response.get_json()["diagram"] == "graph TD; A-->B"

    # --- Decision Context Tests ---

    def test_record_decision_success(self, client, mock_managers):
        mock_managers["decision_context"].record_decision.return_value = "dec_123"

        payload = {"decision": "Use SQL", "reasoning": "Persistence", "category": "DB", "context": {"issue": "storage"}}

        response = client.post("/api/analysis/decisions/record", json=payload)

        assert response.status_code == 201
        assert response.get_json()["decision_id"] == "dec_123"

    def test_record_decision_missing_fields(self, client):
        response = client.post("/api/analysis/decisions/record", json={"decision": "incomplete"})
        assert response.status_code == 400

    def test_find_similar_decisions_success(self, client, mock_managers):
        mock_dec = MagicMock()
        mock_dec.to_dict.return_value = {"decision": "similar one"}
        mock_managers["decision_context"].find_similar_decisions.return_value = [mock_dec]

        response = client.post("/api/analysis/decisions/similar", json={"problem": "how to store data"})

        assert response.status_code == 200
        assert len(response.get_json()["similar_decisions"]) == 1

    def test_update_decision_outcome_success(self, client, mock_managers):
        mock_managers["decision_context"].update_outcome.return_value = True

        response = client.put("/api/analysis/decisions/outcome/dec_123", json={"success": True})

        assert response.status_code == 200
        assert response.get_json()["status"] == "success"

    def test_update_decision_outcome_not_found(self, client, mock_managers):
        mock_managers["decision_context"].update_outcome.return_value = False

        response = client.put("/api/analysis/decisions/outcome/unknown", json={"success": False})
        assert response.status_code == 404

    def test_generic_exception_handling(self, client, mock_managers):
        # Trigger an unhandled exception in any manager
        mock_managers["cross_ref"].compare_documents.side_effect = Exception("Analysis Engine Failure")

        response = client.post("/api/analysis/cross-reference/compare", json={"doc1_path": "a.md", "doc2_path": "b.md"})

        assert response.status_code == 500
        assert "Analysis Engine Failure" in response.get_json()["error"]
