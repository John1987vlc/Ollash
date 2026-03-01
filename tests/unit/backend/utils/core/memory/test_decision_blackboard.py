"""Unit tests for DecisionBlackboard.

All tests use pytest's tmp_path fixture — no real filesystem paths are hardcoded.
"""

import pytest

from backend.utils.core.memory.decision_blackboard import DecisionBlackboard


@pytest.mark.unit
class TestDecisionBlackboard:
    """Tests for CRUD operations on DecisionBlackboard."""

    @pytest.fixture()
    def board(self, tmp_path):
        """Provide a fresh DecisionBlackboard backed by a temp SQLite file."""
        return DecisionBlackboard(tmp_path / "decisions.db")

    # ------------------------------------------------------------------
    # record + retrieve
    # ------------------------------------------------------------------

    def test_record_and_retrieve_decision(self, board):
        board.record_decision("database", "SQLite", "Simple and local")
        result = board.get_decision("database")
        assert result == "SQLite"

    def test_get_decision_missing_key_returns_none(self, board):
        assert board.get_decision("nonexistent") is None

    def test_record_without_context(self, board):
        board.record_decision("auth", "JWT")
        assert board.get_decision("auth") == "JWT"

    # ------------------------------------------------------------------
    # Upsert (same key → update)
    # ------------------------------------------------------------------

    def test_upsert_decision_updates_value(self, board):
        board.record_decision("db", "SQLite", "first choice")
        board.record_decision("db", "PostgreSQL", "scaled up")
        assert board.get_decision("db") == "PostgreSQL"

    def test_upsert_keeps_single_row(self, board):
        board.record_decision("key", "v1")
        board.record_decision("key", "v2")
        decisions = board.get_all_decisions()
        matching = [d for d in decisions if d["key"] == "key"]
        assert len(matching) == 1

    # ------------------------------------------------------------------
    # get_all_decisions
    # ------------------------------------------------------------------

    def test_get_all_decisions_empty(self, board):
        assert board.get_all_decisions() == []

    def test_get_all_decisions_multiple(self, board):
        board.record_decision("k1", "v1")
        board.record_decision("k2", "v2")
        all_d = board.get_all_decisions()
        assert len(all_d) == 2
        keys = {d["key"] for d in all_d}
        assert keys == {"k1", "k2"}

    def test_get_all_decisions_ordered_by_insertion(self, board):
        """Records are returned in insertion order (recorded_at ascending)."""
        board.record_decision("first", "1")
        board.record_decision("second", "2")
        all_d = board.get_all_decisions()
        assert all_d[0]["key"] == "first"
        assert all_d[1]["key"] == "second"

    # ------------------------------------------------------------------
    # format_for_prompt
    # ------------------------------------------------------------------

    def test_format_for_prompt_empty_returns_empty_string(self, board):
        assert board.format_for_prompt() == ""

    def test_format_for_prompt_contains_header(self, board):
        board.record_decision("framework", "FastAPI", "High performance")
        result = board.format_for_prompt()
        assert "## ESTABLISHED DESIGN DECISIONS" in result

    def test_format_for_prompt_includes_key_value(self, board):
        board.record_decision("auth", "JWT")
        result = board.format_for_prompt()
        assert "auth: JWT" in result

    def test_format_for_prompt_includes_context_in_parens(self, board):
        board.record_decision("db", "SQLite", "Chosen for simplicity")
        result = board.format_for_prompt()
        assert "(Chosen for simplicity)" in result

    def test_format_for_prompt_no_context_no_parens(self, board):
        board.record_decision("db", "SQLite")
        result = board.format_for_prompt()
        assert "(" not in result

    # ------------------------------------------------------------------
    # clear
    # ------------------------------------------------------------------

    def test_clear_removes_all_decisions(self, board):
        board.record_decision("x", "1")
        board.clear()
        assert board.get_all_decisions() == []
        assert board.format_for_prompt() == ""

    # ------------------------------------------------------------------
    # DB creation
    # ------------------------------------------------------------------

    def test_db_file_created_automatically(self, tmp_path):
        db_path = tmp_path / "subdir" / "decisions.db"
        board = DecisionBlackboard(db_path)
        board.record_decision("k", "v")
        assert db_path.exists()
