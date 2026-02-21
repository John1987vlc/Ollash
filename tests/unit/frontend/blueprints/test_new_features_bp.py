import io
import sys
from unittest.mock import MagicMock, patch, PropertyMock
import pytest
from flask import Flask
from frontend.blueprints import register_blueprints


@pytest.fixture
def app(tmp_path):
    """Create and configure a new app instance for each test."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["ollash_root_dir"] = tmp_path

    # Mock services
    mock_event_publisher = MagicMock()
    mock_chat_event_bridge = MagicMock()
    mock_alert_manager = MagicMock()
    mock_logger = MagicMock()
    app.config["logger"] = mock_logger

    register_blueprints(
        app=app,
        ollash_root_dir=tmp_path,
        event_publisher=mock_event_publisher,
        chat_event_bridge=mock_chat_event_bridge,
        alert_manager=mock_alert_manager,
    )

    return app


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


class TestMultimodalBlueprint:
    def test_upload_no_file(self, client):
        resp = client.post("/api/multimodal/upload")
        assert resp.status_code == 400
        assert "No file part" in resp.get_json()["error"]

    def test_upload_success(self, client, tmp_path):
        data = {"file": (io.BytesIO(b"fake image data"), "test.png")}

        # Get the module from sys.modules to ensure we are patching the module and not the Blueprint object
        multimodal_module = sys.modules.get("frontend.blueprints.multimodal_bp")

        with patch.object(multimodal_module, "logger") as mock_log:
            # Inject ollash_root_dir via environ_base
            resp = client.post(
                "/api/multimodal/upload",
                data=data,
                content_type="multipart/form-data",
                environ_base={"ollash_root_dir": str(tmp_path)},
            )
            assert resp.status_code == 200
            json_data = resp.get_json()
            assert json_data["status"] == "success"
            assert json_data["filename"] == "test.png"

            # Verify file exists
            uploaded_path = tmp_path / "knowledge_workspace" / "ingest" / "uploads" / "test.png"
            assert uploaded_path.exists()


class TestSandboxBlueprint:
    def test_execute_no_code(self, client):
        resp = client.post("/api/sandbox/execute", json={})
        assert resp.status_code == 400
        assert "No code provided" in resp.get_json()["error"]

    def test_execute_python_success(self, client):
        code = "print('Hello World')"

        from backend.utils.core.tools.wasm_sandbox import DockerSandbox

        with patch.object(DockerSandbox, "is_available", new_callable=PropertyMock) as mock_avail:
            mock_avail.return_value = False
            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "Hello World\n"
                mock_run.return_value.stderr = ""

                resp = client.post("/api/sandbox/execute", json={"code": code, "language": "python"})

                assert resp.status_code == 200
                data = resp.get_json()
                assert data["status"] == "success"
                assert "Hello World" in data["output"]

    def test_execute_unsupported_language(self, client):
        resp = client.post("/api/sandbox/execute", json={"code": "some code", "language": "cobol"})
        assert resp.status_code == 400
        assert "not supported" in resp.get_json()["error"]


class TestExportBlueprint:
    def test_report_generation_started(self, client):
        with patch("backend.utils.core.feedback.activity_report_generator.ActivityReportGenerator") as mock_gen:
            mock_gen_instance = mock_gen.return_value
            mock_gen_instance.generate_executive_report.return_value = "report.pdf"

            resp = client.post("/api/export/report/test_project")
            assert resp.status_code == 200
            assert resp.get_json()["status"] == "success"
