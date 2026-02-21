import pytest
import json
import sqlite3
from unittest.mock import MagicMock

from backend.utils.core.memory.episodic_memory import EpisodicMemory, EpisodicEntry, DecisionRecord


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def episodic_memory(tmp_path, mock_logger):
    return EpisodicMemory(tmp_path, mock_logger)


class TestEpisodicMemory:
    """Test suite for Long-Term Episodic Memory."""

    def test_init_db(self, episodic_memory, tmp_path):
        db_path = tmp_path / "episodic_index.db"
        assert db_path.exists()

        # Verify tables exist
        with sqlite3.connect(str(db_path)) as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            table_names = [t[0] for t in tables]
            assert "episodes" in table_names
            assert "sessions" in table_names
            assert "decisions" in table_names
            assert "episode_embeddings" in table_names

    def test_session_management(self, episodic_memory):
        session_id = episodic_memory.start_session("test_project")
        assert len(session_id) == 8

        # Check in DB
        with sqlite3.connect(str(episodic_memory._db_path)) as conn:
            row = conn.execute("SELECT project_name FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            assert row[0] == "test_project"

        episodic_memory.end_session(session_id, "Summary text")
        with sqlite3.connect(str(episodic_memory._db_path)) as conn:
            row = conn.execute("SELECT summary, ended_at FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            assert row[0] == "Summary text"
            assert row[1] is not None

    def test_record_decision(self, episodic_memory):
        session_id = episodic_memory.start_session("p1")
        decision = DecisionRecord(
            session_id=session_id,
            decision_type="architecture",
            context="Choosing database",
            choice="SQLite",
            reasoning="Simplicity",
        )

        episodic_memory.record_decision(decision)

        recalled = episodic_memory.recall_decisions(decision_type="architecture")
        assert len(recalled) == 1
        assert recalled[0].choice == "SQLite"
        assert recalled[0].session_id == session_id

    def test_recall_decisions_filtering(self, episodic_memory):
        s_id = episodic_memory.start_session("p1")
        episodic_memory.record_decision(DecisionRecord(s_id, "type1", "context1", "c1", "r1"))
        episodic_memory.record_decision(DecisionRecord(s_id, "type2", "context2", "c2", "r2"))

        # Filter by type
        assert len(episodic_memory.recall_decisions(decision_type="type1")) == 1
        # Filter by keyword
        assert len(episodic_memory.recall_decisions(context_keyword="context2")) == 1
        # Limit
        assert len(episodic_memory.recall_decisions(max_results=1)) == 1

    def test_record_episode(self, episodic_memory, tmp_path):
        entry = EpisodicEntry(
            project_name="proj_a",
            phase_name="phase_1",
            error_type="SyntaxError",
            error_pattern_id="syn_001",
            error_description="Missing colon",
            solution_applied="Add colon",
            outcome="success",
            language="python",
        )

        episodic_memory.record_episode(entry)

        # Verify JSON persistence
        json_file = tmp_path / "proj_a" / "episodes.json"
        assert json_file.exists()
        data = json.loads(json_file.read_text())
        assert data[0]["error_type"] == "SyntaxError"

        # Verify DB query
        solutions = episodic_memory.query_solutions("SyntaxError", language="python")
        assert len(solutions) == 1
        assert solutions[0].solution_applied == "Add colon"

    def test_record_episode_with_embedding(self, episodic_memory):
        entry = EpisodicEntry(
            project_name="proj_b",
            phase_name="p1",
            error_type="E1",
            error_pattern_id="pat1",
            error_description="desc",
            solution_applied="sol",
            outcome="success",
        )
        embedding = [0.1, 0.2, 0.3]

        episodic_memory.record_episode_with_embedding(entry, embedding)

        with sqlite3.connect(str(episodic_memory._db_path)) as conn:
            row = conn.execute("SELECT embedding_json FROM episode_embeddings").fetchone()
            assert json.loads(row[0]) == embedding

    def test_query_similar_solutions(self, episodic_memory):
        # Setup entries with embeddings
        e1 = EpisodicEntry("p", "f", "T1", "pat1", "connection timeout", "retry", "success")
        e2 = EpisodicEntry("p", "f", "T2", "pat2", "auth failed", "check keys", "success")

        episodic_memory.record_episode_with_embedding(e1, [1.0, 0.0])
        episodic_memory.record_episode_with_embedding(e2, [0.0, 1.0])

        mock_cache = MagicMock()
        # Mocking embedding for "timeout error" to be similar to [1.0, 0.0]
        mock_cache.get.return_value = [0.9, 0.1]

        results = episodic_memory.query_similar_solutions("timeout error", mock_cache, threshold=0.8)
        assert len(results) == 1
        assert results[0].error_type == "T1"

    def test_get_statistics(self, episodic_memory):
        episodic_memory.record_episode(EpisodicEntry("p", "f", "E1", "pat1", "d", "s", "success"))
        episodic_memory.record_episode(EpisodicEntry("p", "f", "E2", "pat1", "d", "s", "failure"))

        stats = episodic_memory.get_statistics()
        assert stats["total_episodes"] == 2
        assert stats["successful_solutions"] == 1
        assert stats["success_rate"] == 0.5
        assert stats["unique_error_patterns"] == 1
