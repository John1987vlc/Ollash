"""Tests for PipelineStore — pipeline CRUD, run lifecycle, builtin seeding."""

import pytest

from backend.utils.core.system.db.pipeline_store import PipelineStore

pytestmark = pytest.mark.unit


@pytest.fixture
def store(tmp_path):
    return PipelineStore(tmp_path / "pipelines.db")


class TestPipelineCRUD:
    def test_create_and_get(self, store):
        p = store.create_pipeline("My Pipeline", ["SecurityScanPhase", "SeniorReviewPhase"], "A description")
        assert p["name"] == "My Pipeline"
        assert p["phases"] == ["SecurityScanPhase", "SeniorReviewPhase"]
        assert p["description"] == "A description"
        assert p["id"] is not None
        assert p["builtin"] is False

    def test_get_nonexistent_returns_none(self, store):
        assert store.get_pipeline(9999) is None

    def test_list_pipelines_empty(self, store):
        assert store.list_pipelines() == []

    def test_list_pipelines(self, store):
        store.create_pipeline("P1", ["SecurityScanPhase"])
        store.create_pipeline("P2", ["SeniorReviewPhase"])
        pipelines = store.list_pipelines()
        assert len(pipelines) == 2
        names = {p["name"] for p in pipelines}
        assert "P1" in names and "P2" in names

    def test_update_pipeline(self, store):
        p = store.create_pipeline("Old", ["SecurityScanPhase"])
        updated = store.update_pipeline(p["id"], name="New", phases=["SeniorReviewPhase", "VerificationPhase"])
        assert updated["name"] == "New"
        assert updated["phases"] == ["SeniorReviewPhase", "VerificationPhase"]

    def test_update_nonexistent_returns_none(self, store):
        assert store.update_pipeline(9999, name="X") is None

    def test_delete_user_pipeline(self, store):
        p = store.create_pipeline("Temp", ["SecurityScanPhase"])
        deleted = store.delete_pipeline(p["id"])
        assert deleted is True
        assert store.get_pipeline(p["id"]) is None

    def test_delete_nonexistent_returns_false(self, store):
        assert store.delete_pipeline(9999) is False

    def test_builtin_pipeline_cannot_be_deleted(self, store):
        store.seed_builtins()
        pipelines = store.list_pipelines()
        builtin = next(p for p in pipelines if p["builtin"])
        deleted = store.delete_pipeline(builtin["id"])
        assert deleted is False  # builtin protection
        assert store.get_pipeline(builtin["id"]) is not None


class TestBuiltins:
    def test_seed_inserts_four_pipelines(self, store):
        store.seed_builtins()
        pipelines = store.list_pipelines()
        assert len(pipelines) == 4

    def test_seed_idempotent(self, store):
        store.seed_builtins()
        store.seed_builtins()
        assert len(store.list_pipelines()) == 4

    def test_builtin_pipelines_marked(self, store):
        store.seed_builtins()
        for p in store.list_pipelines():
            assert p["builtin"] is True

    def test_quick_review_builtin_exists(self, store):
        store.seed_builtins()
        names = {p["name"] for p in store.list_pipelines()}
        assert "Quick Review" in names

    def test_refactor_builtin_phases(self, store):
        store.seed_builtins()
        refactor = next(p for p in store.list_pipelines() if p["name"] == "Refactor")
        assert "LogicPlanningPhase" in refactor["phases"]
        assert "FileRefinementPhase" in refactor["phases"]


class TestRunLifecycle:
    def test_create_run(self, store):
        p = store.create_pipeline("P", ["SecurityScanPhase"])
        run = store.create_run(p["id"], "/tmp/project")
        assert run["status"] == "running"
        assert run["project_path"] == "/tmp/project"
        assert run["log"] == []
        assert run["id"] is not None

    def test_append_log(self, store):
        p = store.create_pipeline("P", ["SecurityScanPhase"])
        run = store.create_run(p["id"])
        store.append_log(run["id"], {"type": "phase_started", "phase": "SecurityScanPhase"})
        store.append_log(run["id"], {"type": "phase_done", "phase": "SecurityScanPhase"})
        updated = store.get_run(run["id"])
        assert len(updated["log"]) == 2
        assert updated["log"][0]["type"] == "phase_started"

    def test_finish_run_completed(self, store):
        p = store.create_pipeline("P", ["SecurityScanPhase"])
        run = store.create_run(p["id"])
        store.finish_run(run["id"], "completed")
        updated = store.get_run(run["id"])
        assert updated["status"] == "completed"
        assert updated["finished_at"] is not None

    def test_finish_run_failed(self, store):
        p = store.create_pipeline("P", ["SecurityScanPhase"])
        run = store.create_run(p["id"])
        store.finish_run(run["id"], "failed")
        assert store.get_run(run["id"])["status"] == "failed"

    def test_list_runs(self, store):
        p = store.create_pipeline("P", ["SecurityScanPhase"])
        store.create_run(p["id"])
        store.create_run(p["id"])
        runs = store.list_runs(p["id"])
        assert len(runs) == 2

    def test_list_runs_respects_limit(self, store):
        p = store.create_pipeline("P", ["SecurityScanPhase"])
        for _ in range(5):
            store.create_run(p["id"])
        assert len(store.list_runs(p["id"], limit=3)) == 3
