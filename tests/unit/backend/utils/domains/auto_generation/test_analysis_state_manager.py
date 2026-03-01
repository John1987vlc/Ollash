"""Unit tests for AnalysisStateManager (E1)."""

import pytest
from unittest.mock import MagicMock


@pytest.mark.unit
class TestAnalysisStateManager:
    """Tests for incremental differential analysis state management."""

    @pytest.fixture
    def logger(self):
        return MagicMock()

    @pytest.fixture
    def manager(self, logger):
        from backend.utils.domains.auto_generation.analysis_state_manager import AnalysisStateManager

        return AnalysisStateManager(logger=logger)

    def test_load_snapshot_returns_none_when_missing(self, manager, tmp_path):
        result = manager.load_snapshot(tmp_path)
        assert result is None

    def test_save_and_load_roundtrip(self, manager, tmp_path):
        files = {"src/app.py": "x = 1\n", "README.md": "# Hello\n"}
        analysis = {"total_lines_of_code": 2, "code_patterns": ["type_hints"]}

        manager.save_snapshot(tmp_path, "myproject", files, analysis)
        snapshot = manager.load_snapshot(tmp_path)

        assert snapshot is not None
        assert snapshot.project_name == "myproject"
        assert "src/app.py" in snapshot.file_snapshots
        assert snapshot.full_analysis["total_lines_of_code"] == 2

    def test_load_snapshot_returns_none_for_invalid_json(self, manager, tmp_path):
        state_dir = tmp_path / ".ollash" / "analysis_state"
        state_dir.mkdir(parents=True)
        (state_dir / "snapshot.json").write_text("not valid json")

        result = manager.load_snapshot(tmp_path)
        assert result is None

    def test_compute_changed_files_returns_only_modified(self, manager, tmp_path):
        files_v1 = {"a.py": "x = 1\n", "b.py": "y = 2\n"}
        analysis = {}
        snapshot = manager.save_snapshot(tmp_path, "p", files_v1, analysis)

        # Load snapshot and simulate a change in a.py
        snapshot = manager.load_snapshot(tmp_path)
        files_v2 = {"a.py": "x = 99\n", "b.py": "y = 2\n"}  # a.py changed
        changed = manager.compute_changed_files(files_v2, snapshot)

        assert "a.py" in changed
        assert "b.py" not in changed

    def test_compute_changed_files_returns_empty_when_identical(self, manager, tmp_path):
        files = {"a.py": "x = 1\n", "b.py": "y = 2\n"}
        manager.save_snapshot(tmp_path, "p", files, {})
        snapshot = manager.load_snapshot(tmp_path)

        changed = manager.compute_changed_files(files, snapshot)
        assert changed == {}

    def test_compute_changed_files_includes_new_files(self, manager, tmp_path):
        files_v1 = {"a.py": "x = 1\n"}
        manager.save_snapshot(tmp_path, "p", files_v1, {})
        snapshot = manager.load_snapshot(tmp_path)

        files_v2 = {"a.py": "x = 1\n", "b.py": "new file\n"}
        changed = manager.compute_changed_files(files_v2, snapshot)

        assert "b.py" in changed
        assert "a.py" not in changed

    def test_merge_analysis_updates_file_details(self, manager):
        previous = {
            "total_lines_of_code": 10,
            "file_details": [
                {"path": "a.py", "lines": 5},
                {"path": "b.py", "lines": 5},
            ],
            "files_by_type": {"python": 2},
            "code_patterns": ["type_hints"],
            "dependencies": ["flask"],
        }
        delta = {
            "total_lines_of_code": 8,
            "file_details": [{"path": "a.py", "lines": 8}],
            "files_by_type": {"python": 1},
            "code_patterns": ["async_patterns"],
            "dependencies": ["requests"],
        }

        merged = manager.merge_analysis(previous, delta, {"a.py"})

        # a.py should have updated lines count
        a_detail = next(d for d in merged["file_details"] if d["path"] == "a.py")
        assert a_detail["lines"] == 8

        # b.py should still exist
        b_detail = next(d for d in merged["file_details"] if d["path"] == "b.py")
        assert b_detail["lines"] == 5

        # total LOC should be recalculated
        assert merged["total_lines_of_code"] == 13  # 8 + 5

    def test_merge_analysis_deduplicates_patterns(self, manager):
        previous = {
            "file_details": [],
            "total_lines_of_code": 0,
            "files_by_type": {},
            "code_patterns": ["type_hints", "async_patterns"],
            "dependencies": [],
        }
        delta = {
            "file_details": [],
            "total_lines_of_code": 0,
            "files_by_type": {},
            "code_patterns": ["type_hints", "error_handling"],
            "dependencies": [],
        }

        merged = manager.merge_analysis(previous, delta, set())

        # type_hints should appear only once
        assert merged["code_patterns"].count("type_hints") == 1
        assert "error_handling" in merged["code_patterns"]

    def test_atomic_write_cleans_up_tmp_file(self, manager, tmp_path):
        files = {"src/app.py": "x = 1\n"}
        manager.save_snapshot(tmp_path, "p", files, {})

        # .tmp file should not exist after save
        tmp_file = tmp_path / ".ollash" / "analysis_state" / "snapshot.tmp"
        assert not tmp_file.exists()
