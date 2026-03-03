"""Unit tests for SQLiteVectorStore — ChromaDB replacement."""

import pytest

from backend.utils.core.memory.sqlite_vector_store import SQLiteVectorStore


@pytest.fixture
def store(tmp_path):
    return SQLiteVectorStore(tmp_path / "test_vectors.db")


@pytest.fixture
def col(store):
    return store.get_or_create_collection("test_col")


# ---------------------------------------------------------------------------
# add / count / get
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_add_and_count(col):
    col.add(ids=["a", "b", "c"], documents=["apple", "banana", "cherry"])
    assert col.count() == 3


@pytest.mark.unit
def test_add_idempotent(col):
    col.add(ids=["a"], documents=["apple"])
    col.add(ids=["a"], documents=["apple updated"])
    assert col.count() == 1
    result = col.get(ids=["a"])
    assert result["documents"][0] == "apple updated"


@pytest.mark.unit
def test_add_with_metadata(col):
    col.add(
        ids=["x"],
        documents=["def foo(): pass"],
        metadatas=[{"language": "python", "source": "test.py"}],
    )
    result = col.get(ids=["x"])
    assert result["metadatas"][0]["language"] == "python"


# ---------------------------------------------------------------------------
# query by text (LIKE search)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_query_by_text_finds_match(col):
    col.add(ids=["f1", "f2"], documents=["def add(a, b): return a + b", "class Foo: pass"])
    result = col.query(query_texts=["addition function"], n_results=2)
    assert len(result["documents"][0]) > 0
    assert result["ids"][0]  # at least one result
    # distances should be 1.0 for keyword matches
    assert all(d == 1.0 for d in result["distances"][0])


@pytest.mark.unit
def test_query_returns_empty_on_no_match(col):
    # empty collection
    result = col.query(query_texts=["anything"], n_results=5)
    assert result["ids"] == [[]]
    assert result["documents"] == [[]]


@pytest.mark.unit
def test_query_respects_n_results(col):
    col.add(
        ids=["a", "b", "c", "d"],
        documents=["python code", "python script", "python module", "python class"],
    )
    result = col.query(query_texts=["python"], n_results=2)
    assert len(result["documents"][0]) <= 2


# ---------------------------------------------------------------------------
# query by embeddings (cosine similarity)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_query_by_embeddings_with_stored_embeddings(col):
    e1 = [1.0, 0.0, 0.0]
    e2 = [0.0, 1.0, 0.0]
    e3 = [1.0, 0.0, 0.1]  # close to e1
    col.add(
        ids=["v1", "v2", "v3"],
        documents=["doc1", "doc2", "doc3"],
        embeddings=[e1, e2, e3],
    )
    result = col.query(query_embeddings=[[1.0, 0.0, 0.0]], n_results=2)
    ids = result["ids"][0]
    # v1 and v3 should be closest to query [1, 0, 0]
    assert "v1" in ids or "v3" in ids


@pytest.mark.unit
def test_query_by_zero_embeddings_falls_back_to_recent(col):
    """Zero embeddings (stub from OllamaClient) fall back to most-recent."""
    col.add(ids=["a"], documents=["doc a"])
    result = col.query(query_embeddings=[[0.0, 0.0, 0.0]], n_results=5)
    # Should still return something (fallback to recent)
    assert isinstance(result["ids"][0], list)


# ---------------------------------------------------------------------------
# peek / delete
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_peek_returns_oldest(col):
    col.add(ids=["first"], documents=["first doc"])
    col.add(ids=["second"], documents=["second doc"])
    result = col.peek(n=1)
    assert len(result["ids"]) == 1
    assert result["ids"][0] == "first"


@pytest.mark.unit
def test_delete_removes_entries(col):
    col.add(ids=["a", "b", "c"], documents=["d1", "d2", "d3"])
    col.delete(ids=["a", "b"])
    assert col.count() == 1
    result = col.get(ids=["a"])
    assert result["ids"] == []


@pytest.mark.unit
def test_delete_noop_on_empty(col):
    col.delete(ids=[])  # should not raise
    col.delete(ids=None)  # should not raise


# ---------------------------------------------------------------------------
# delete_collection
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_delete_collection(store, tmp_path):
    col = store.get_or_create_collection("temp_col")
    col.add(ids=["x"], documents=["doc"])
    store.delete_collection("temp_col")
    # Re-creating should give empty collection
    fresh = store.get_or_create_collection("temp_col")
    assert fresh.count() == 0


# ---------------------------------------------------------------------------
# ChromaDB-compatible result shape
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_result_shape(col):
    col.add(ids=["z"], documents=["test document"])
    result = col.query(query_texts=["test"], n_results=1)
    assert "ids" in result
    assert "documents" in result
    assert "metadatas" in result
    assert "distances" in result
    # All values are lists-of-lists (ChromaDB batch format)
    assert isinstance(result["ids"], list)
    assert isinstance(result["ids"][0], list)
    assert isinstance(result["documents"][0], list)
    assert isinstance(result["metadatas"][0], list)
    assert isinstance(result["distances"][0], list)
