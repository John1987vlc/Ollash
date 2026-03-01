"""Unit tests for PUT /api/hil/edit-task/<task_id> — Feature 5."""

import pytest
from unittest.mock import MagicMock, patch


def _make_app():
    from flask import Flask
    from frontend.blueprints.hil_bp import hil_bp

    app = Flask(__name__)
    app.register_blueprint(hil_bp)
    app.config["TESTING"] = True
    return app


@pytest.mark.unit
class TestHilEditTask:
    def _client(self):
        return _make_app().test_client()

    def _make_mock_dag_node(self, status_value="PENDING"):
        from unittest.mock import MagicMock

        node = MagicMock()

        # Simulate TaskStatus enum
        status_enum = MagicMock()
        status_enum.value = status_value
        node.status = status_enum
        node.task_data = {"instruction": "old instruction"}
        return node

    def _patch_orchestrators(self, node=None):
        """Return a context manager that patches _get_active_orchestrators."""
        ao = MagicMock()
        dag = MagicMock()
        orch = MagicMock()
        orch._current_dag = dag
        ao.list_active.return_value = {"my_project": orch}
        dag.get_node.return_value = node
        return ao

    def test_returns_400_for_empty_instruction(self):
        client = self._client()
        resp = client.put(
            "/api/hil/edit-task/task-001",
            json={"instruction": ""},
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert b"instruction" in resp.data.lower()

    def test_returns_404_when_no_orchestrators(self):
        with patch("frontend.blueprints.hil_bp._get_active_orchestrators", return_value=None):
            client = self._client()
            resp = client.put(
                "/api/hil/edit-task/task-001",
                json={"instruction": "do something"},
                content_type="application/json",
            )
        assert resp.status_code == 404

    def test_returns_404_when_task_not_found(self):
        ao = self._patch_orchestrators(node=None)
        with patch("frontend.blueprints.hil_bp._get_active_orchestrators", return_value=ao):
            with patch("backend.agents.orchestrators.task_dag.TaskStatus") as mock_status:
                client = self._client()
                resp = client.put(
                    "/api/hil/edit-task/nonexistent",
                    json={"instruction": "do something"},
                    content_type="application/json",
                )
        assert resp.status_code == 404

    def test_returns_409_for_non_pending_node(self):
        from unittest.mock import MagicMock

        node = self._make_mock_dag_node(status_value="IN_PROGRESS")
        ao = self._patch_orchestrators(node=node)

        with patch("frontend.blueprints.hil_bp._get_active_orchestrators", return_value=ao):
            # Patch TaskStatus so the comparison works
            with patch(
                "frontend.blueprints.hil_bp.edit_task.__code__",
                wraps=None,
            ):
                pass

        # Direct functional test by making TaskStatus.PENDING not match node.status
        from backend.agents.orchestrators.task_dag import TaskStatus as RealTaskStatus

        node2 = MagicMock()
        node2.status = RealTaskStatus.IN_PROGRESS
        node2.task_data = {}
        ao2 = self._patch_orchestrators(node=node2)

        with patch("frontend.blueprints.hil_bp._get_active_orchestrators", return_value=ao2):
            client = self._client()
            resp = client.put(
                "/api/hil/edit-task/task-001",
                json={"instruction": "do something"},
                content_type="application/json",
            )
        assert resp.status_code == 409

    def test_returns_updated_for_pending_node(self):
        from backend.agents.orchestrators.task_dag import TaskStatus as RealTaskStatus

        node = MagicMock()
        node.status = RealTaskStatus.PENDING
        node.task_data = {"instruction": "old"}
        ao = self._patch_orchestrators(node=node)

        with patch("frontend.blueprints.hil_bp._get_active_orchestrators", return_value=ao):
            client = self._client()
            resp = client.put(
                "/api/hil/edit-task/task-001",
                json={"instruction": "new instruction"},
                content_type="application/json",
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "updated"

    def test_updates_task_data_instruction(self):
        from backend.agents.orchestrators.task_dag import TaskStatus as RealTaskStatus

        node = MagicMock()
        node.status = RealTaskStatus.PENDING
        node.task_data = {"instruction": "old"}
        ao = self._patch_orchestrators(node=node)

        with patch("frontend.blueprints.hil_bp._get_active_orchestrators", return_value=ao):
            client = self._client()
            client.put(
                "/api/hil/edit-task/task-001",
                json={"instruction": "brand new instruction"},
                content_type="application/json",
            )
        assert node.task_data["instruction"] == "brand new instruction"
