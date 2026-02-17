"""
Comprehensive unit tests for all new features added to Ollash.

Covers: exceptions hierarchy, type definitions, embedding cache enhancements,
episodic memory enhancements, prompt tuner enhancements, base phase,
phase groups, docker sandbox, async command executor, image analyzer,
and multi-provider manager.
"""

import asyncio
import json
import struct
import zlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Note: conftest.py provides autouse mock_chromadb_client fixture


# ============================================================
# Helper: create a mock AgentLogger
# ============================================================
def _mock_logger():
    logger = MagicMock()
    logger.info = MagicMock()
    logger.error = MagicMock()
    logger.warning = MagicMock()
    logger.debug = MagicMock()
    return logger


def _make_png(path):
    """Create a minimal 1x1 PNG file."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)
    idat_data = zlib.compress(b"\x00\x00")
    idat_crc = zlib.crc32(b"IDAT" + idat_data) & 0xFFFFFFFF
    idat = struct.pack(">I", len(idat_data)) + b"IDAT" + idat_data + struct.pack(">I", idat_crc)
    iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
    iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)
    Path(path).write_bytes(sig + ihdr + idat + iend)
    return path


# ============================================================
# 1. Exception Hierarchy Tests
# ============================================================
class TestExceptionHierarchy:
    def test_ollash_error_is_base(self):
        from backend.utils.core.exceptions import OllashError

        assert isinstance(OllashError("x"), Exception)

    def test_infrastructure_inherits_ollash(self):
        from backend.utils.core.exceptions import InfrastructureError, OllashError

        assert isinstance(InfrastructureError("x"), OllashError)

    def test_resource_exhaustion(self):
        from backend.utils.core.exceptions import ResourceExhaustionError, InfrastructureError

        e = ResourceExhaustionError("GPU", "out of VRAM")
        assert isinstance(e, InfrastructureError)
        assert e.resource == "GPU"
        assert "GPU" in str(e) and "VRAM" in str(e)

    def test_sandbox_unavailable(self):
        from backend.utils.core.exceptions import SandboxUnavailableError, InfrastructureError

        e = SandboxUnavailableError(["docker", "wasmtime"])
        assert isinstance(e, InfrastructureError)
        assert e.attempted_runtimes == ["docker", "wasmtime"]
        assert "docker" in str(e)

    def test_sandbox_unavailable_empty(self):
        from backend.utils.core.exceptions import SandboxUnavailableError

        assert SandboxUnavailableError().attempted_runtimes == []

    def test_network_timeout(self):
        from backend.utils.core.exceptions import NetworkTimeoutError, InfrastructureError

        e = NetworkTimeoutError("fetch", 30.0)
        assert isinstance(e, InfrastructureError)
        assert e.operation == "fetch" and e.timeout_seconds == 30.0

    def test_agent_logic_error(self):
        from backend.utils.core.exceptions import AgentLogicError, OllashError

        assert isinstance(AgentLogicError("x"), OllashError)

    def test_invalid_tool_output_truncates(self):
        from backend.utils.core.exceptions import InvalidToolOutputError, AgentLogicError

        e = InvalidToolOutputError("tool", "bad", "x" * 1000)
        assert isinstance(e, AgentLogicError)
        assert e.tool_name == "tool"
        assert len(e.raw_output) <= 500

    def test_phase_contract_violation(self):
        from backend.utils.core.exceptions import PhaseContractViolationError

        e = PhaseContractViolationError("Review", "no files")
        assert e.phase_name == "Review" and e.violation == "no files"

    def test_prompt_parsing_truncates(self):
        from backend.utils.core.exceptions import PromptParsingError

        e = PromptParsingError("json", "z" * 1000)
        assert e.expected_format == "json"
        assert len(e.raw_response) <= 500

    def test_ollama_backward_compat(self):
        from backend.utils.core.exceptions import OllamaError, InfrastructureError

        assert isinstance(OllamaError("x"), InfrastructureError)

    def test_agent_loop_dual_inheritance(self):
        from backend.utils.core.exceptions import AgentLoopError, AgentError, AgentLogicError

        e = AgentLoopError("stuck")
        assert isinstance(e, AgentError)
        assert isinstance(e, AgentLogicError)

    def test_parallel_phase_error(self):
        from backend.utils.core.exceptions import ParallelPhaseError, PipelineError

        e = ParallelPhaseError({"A": "err_a", "B": "err_b"})
        assert isinstance(e, PipelineError)
        assert "A" in str(e) and "B" in str(e)

    def test_provider_errors(self):
        from backend.utils.core.exceptions import (
            ProviderError,
            ProviderConnectionError,
            ProviderAuthenticationError,
            OllashError,
        )

        assert issubclass(ProviderError, OllashError)
        e1 = ProviderConnectionError("groq", "timeout")
        assert e1.provider_name == "groq"
        e2 = ProviderAuthenticationError("openrouter")
        assert e2.provider_name == "openrouter"


# ============================================================
# 2. Type Definitions Tests
# ============================================================
class TestTypeDefinitions:
    def test_literal_types_importable(self):
        from backend.core.type_definitions import (
            PhaseOutcome,
        )

        assert PhaseOutcome is not None

    def test_phase_result_dict(self):
        from backend.core.type_definitions import PhaseResultDict

        d: PhaseResultDict = {
            "generated_files": {"main.py": "x"},
            "structure": {},
            "file_paths": ["main.py"],
        }
        assert d["file_paths"] == ["main.py"]

    def test_execution_plan_dict_partial(self):
        from backend.core.type_definitions import ExecutionPlanDict

        d: ExecutionPlanDict = {"project_name": "test"}
        assert d["project_name"] == "test"

    def test_tool_dicts(self):
        from backend.core.type_definitions import ToolCallDict, ToolResultDict

        tc: ToolCallDict = {"name": "write_file", "arguments": {"path": "x.py"}}
        tr: ToolResultDict = {"name": "write_file", "result": "ok", "success": True}
        assert tc["name"] == "write_file" and tr["success"] is True

    def test_llm_provider_protocol(self):
        from backend.core.type_definitions import LLMProviderProtocol

        class P:
            async def chat(self, messages, tools=None, temperature=0.5):
                return {}

            async def embed(self, text):
                return [0.1]

            def supports_tools(self):
                return True

            def supports_vision(self):
                return False

        assert isinstance(P(), LLMProviderProtocol)

    def test_model_provider_protocol(self):
        from backend.core.type_definitions import ModelProviderProtocol

        class M:
            def get_client(self, role):
                return None

            def get_embedding_client(self):
                return None

            def get_all_clients(self):
                return {}

        assert isinstance(M(), ModelProviderProtocol)

    def test_tool_executor_protocol(self):
        from backend.core.type_definitions import ToolExecutorProtocol

        class T:
            async def execute_tool(self, tool_name, **kwargs):
                return "ok"

        assert isinstance(T(), ToolExecutorProtocol)


# ============================================================
# 3. EmbeddingCache Enhanced Tests
# ============================================================
class TestEmbeddingCacheEnhanced:
    def test_basic_get_put(self):
        from backend.utils.core.embedding_cache import EmbeddingCache

        c = EmbeddingCache(max_size=100, ttl_seconds=3600)
        c.put("hello", [0.1, 0.2])
        assert c.get("hello") == [0.1, 0.2]

    def test_cache_miss(self):
        from backend.utils.core.embedding_cache import EmbeddingCache

        assert EmbeddingCache().get("nope") is None

    def test_lru_eviction(self):
        from backend.utils.core.embedding_cache import EmbeddingCache

        c = EmbeddingCache(max_size=2)
        c.put("a", [1.0])
        c.put("b", [2.0])
        c.put("c", [3.0])
        assert c.get("a") is None
        assert c.get("b") == [2.0]

    def test_ttl_expiration(self):
        import time
        from backend.utils.core.embedding_cache import EmbeddingCache

        c = EmbeddingCache(ttl_seconds=1)
        c.put("x", [1.0])
        time.sleep(1.1)
        assert c.get("x") is None

    def test_get_batch(self):
        from backend.utils.core.embedding_cache import EmbeddingCache

        c = EmbeddingCache()
        c.put("a", [1.0])
        c.put("b", [2.0])
        r = c.get_batch(["a", "b", "c"])
        assert r["a"] == [1.0] and r["b"] == [2.0] and r["c"] is None

    def test_put_batch(self):
        from backend.utils.core.embedding_cache import EmbeddingCache

        c = EmbeddingCache()
        c.put_batch({"x": [1.0], "y": [2.0]})
        assert c.get("x") == [1.0] and c.get("y") == [2.0]

    def test_memory_usage(self):
        from backend.utils.core.embedding_cache import EmbeddingCache

        c = EmbeddingCache()
        c.put("t", [0.1] * 100)
        assert c.get_memory_usage_bytes() > 0

    def test_stats_new_fields(self):
        from backend.utils.core.embedding_cache import EmbeddingCache

        c = EmbeddingCache()
        c.put("s", [1.0])
        c.get("s")
        c.get("miss")
        s = c.get_stats()
        assert "memory_bytes" in s and "backend" in s
        assert s["hits"] == 1 and s["misses"] == 1

    def test_sqlite_persistence(self, tmp_path):
        from backend.utils.core.embedding_cache import EmbeddingCache

        p = tmp_path / "cache"
        c1 = EmbeddingCache(persist_path=p, persist_backend="sqlite")
        c1.put("saved", [1.0, 2.0])
        c1.save_to_disk()
        c2 = EmbeddingCache(persist_path=p, persist_backend="sqlite")
        assert c2.get("saved") == [1.0, 2.0]

    def test_json_persistence(self, tmp_path):
        from backend.utils.core.embedding_cache import EmbeddingCache

        p = tmp_path / "cache.json"
        c1 = EmbeddingCache(persist_path=p, persist_backend="json")
        c1.put("js", [3.0])
        c1.save_to_disk()
        c2 = EmbeddingCache(persist_path=p, persist_backend="json")
        assert c2.get("js") == [3.0]

    def test_clear(self):
        from backend.utils.core.embedding_cache import EmbeddingCache

        c = EmbeddingCache()
        c.put("x", [1.0])
        c.clear()
        assert c.get("x") is None
        assert c.get_stats()["size"] == 0


# ============================================================
# 4. EpisodicMemory Enhanced Tests
# ============================================================
class TestEpisodicMemoryEnhanced:
    @pytest.fixture
    def memory(self, tmp_path):
        from backend.utils.core.episodic_memory import EpisodicMemory

        return EpisodicMemory(memory_dir=tmp_path / "mem", logger=_mock_logger())

    @pytest.fixture
    def entry(self):
        from backend.utils.core.episodic_memory import EpisodicEntry

        return EpisodicEntry(
            project_name="proj",
            phase_name="review",
            error_type="ImportError",
            error_pattern_id="imp001",
            error_description="No module named 'foo'",
            solution_applied="pip install foo",
            outcome="success",
            language="python",
            file_path="main.py",
        )

    def test_record_and_query(self, memory, entry):
        memory.record_episode(entry)
        r = memory.query_solutions("ImportError", language="python")
        assert len(r) == 1 and r[0].solution_applied == "pip install foo"

    def test_best_solution_none(self, memory):
        assert memory.get_best_solution("x") is None

    def test_success_rate_zero(self, memory):
        assert memory.get_success_rate("x") == 0.0

    def test_statistics_keys(self, memory):
        s = memory.get_statistics()
        for k in ("total_episodes", "total_sessions", "total_decisions"):
            assert k in s

    def test_session_lifecycle(self, memory):
        sid = memory.start_session("proj")
        assert len(sid) == 8
        memory.end_session(sid, "done")
        assert memory.get_statistics()["total_sessions"] == 1

    def test_decision_recording(self, memory):
        from backend.utils.core.episodic_memory import DecisionRecord

        sid = memory.start_session()
        memory.record_decision(
            DecisionRecord(
                session_id=sid,
                decision_type="model",
                context="review",
                choice="deepseek",
                reasoning="best",
            )
        )
        r = memory.recall_decisions(decision_type="model")
        assert len(r) == 1 and r[0].choice == "deepseek"

    def test_recall_with_keyword(self, memory):
        from backend.utils.core.episodic_memory import DecisionRecord

        sid = memory.start_session()
        memory.record_decision(
            DecisionRecord(session_id=sid, decision_type="t", context="file op", choice="a", reasoning="r")
        )
        memory.record_decision(
            DecisionRecord(session_id=sid, decision_type="t", context="network scan", choice="b", reasoning="r")
        )
        r = memory.recall_decisions(context_keyword="network")
        assert len(r) == 1 and r[0].choice == "b"

    def test_decision_record_serde(self):
        from backend.utils.core.episodic_memory import DecisionRecord

        dr = DecisionRecord(session_id="a", decision_type="t", context="c", choice="ch", reasoning="r")
        d = dr.to_dict()
        dr2 = DecisionRecord.from_dict(d)
        assert dr2.choice == "ch"

    def test_episodic_entry_serde(self):
        from backend.utils.core.episodic_memory import EpisodicEntry

        e = EpisodicEntry(
            project_name="p",
            phase_name="ph",
            error_type="E",
            error_pattern_id="e1",
            error_description="d",
            solution_applied="f",
            outcome="success",
        )
        e2 = EpisodicEntry.from_dict(e.to_dict())
        assert e2.outcome == "success"

    def test_cosine_similarity(self, memory):
        assert memory._cosine_similarity([1, 0, 0], [1, 0, 0]) == pytest.approx(1.0)
        assert memory._cosine_similarity([1, 0, 0], [0, 1, 0]) == pytest.approx(0.0)
        assert memory._cosine_similarity([], []) == 0.0
        assert memory._cosine_similarity([1], [1, 2]) == 0.0

    def test_record_with_embedding(self, memory, entry):
        memory.record_episode_with_embedding(entry, [0.1, 0.2])
        assert memory.get_statistics()["total_episodes"] == 1

    def test_query_similar(self, memory, entry):
        memory.record_episode_with_embedding(entry, [1.0, 0.0, 0.0])
        cache = MagicMock()
        cache.get.return_value = [1.0, 0.0, 0.0]
        r = memory.query_similar_solutions("ModuleNotFoundError", cache, threshold=0.5)
        assert len(r) == 1

    def test_query_similar_fallback(self, memory, entry):
        memory.record_episode(entry)
        cache = MagicMock()
        cache.get.return_value = None
        r = memory.query_similar_solutions("ImportError", cache)
        assert len(r) == 1

    def test_async_wrappers(self, memory, entry):
        asyncio.run(memory.async_record_episode(entry))
        r = asyncio.run(memory.async_query_solutions("ImportError"))
        assert len(r) == 1

    def test_async_record_decision(self, memory):
        from backend.utils.core.episodic_memory import DecisionRecord

        sid = memory.start_session()
        asyncio.run(
            memory.async_record_decision(
                DecisionRecord(session_id=sid, decision_type="t", context="c", choice="ch", reasoning="r")
            )
        )
        assert len(memory.recall_decisions()) == 1


# ============================================================
# 5. PromptTuner Enhanced Tests
# ============================================================
class TestPromptTunerEnhanced:
    @pytest.fixture
    def tuner(self, tmp_path):
        from backend.utils.core.prompt_tuner import FeedbackStore, PromptTuner

        store = FeedbackStore(store_dir=tmp_path / "fb")
        return PromptTuner(feedback_store=store, logger=_mock_logger())

    def test_feedback_entry_serde(self):
        from backend.utils.core.prompt_tuner import FeedbackEntry

        fe = FeedbackEntry(prompt_id="p1", original_output="o", user_correction="c", rating=0.3)
        fe2 = FeedbackEntry.from_dict(fe.to_dict())
        assert fe2.rating == 0.3

    def test_store_save_query(self, tmp_path):
        from backend.utils.core.prompt_tuner import FeedbackStore, FeedbackEntry

        s = FeedbackStore(store_dir=tmp_path / "fb2")
        s.save(FeedbackEntry(prompt_id="p1", original_output="o", user_correction="c", rating=0.5))
        s.save(FeedbackEntry(prompt_id="p2", original_output="o", user_correction="c", rating=0.9))
        assert len(s.query(prompt_id="p1")) == 1

    def test_record_feedback(self, tuner):
        tuner.record_feedback("tp", "out", "cor", 0.6)
        assert tuner.get_feedback_summary("tp")["total"] == 1

    def test_few_shot_examples(self, tuner):
        tuner.record_feedback("p1", "bad", "good", 0.3)
        tuner.record_feedback("p1", "bad2", "good2", 0.2)
        ex = tuner.get_few_shot_examples("p1")
        assert len(ex) == 2

    def test_adjust_temp_low(self, tuner):
        from backend.utils.core.prompt_tuner import FeedbackEntry

        for _ in range(5):
            tuner.feedback_store.save(
                FeedbackEntry(prompt_id="p", original_output="o", user_correction="c", rating=0.2)
            )
        assert tuner.adjust_temperature("p", 0.5) < 0.5

    def test_adjust_temp_high(self, tuner):
        from backend.utils.core.prompt_tuner import FeedbackEntry

        for _ in range(5):
            tuner.feedback_store.save(FeedbackEntry(prompt_id="p", original_output="o", user_correction="", rating=0.9))
        assert tuner.adjust_temperature("p", 0.5) > 0.5

    def test_auto_evaluate_empty(self, tuner):
        assert tuner.auto_evaluate("p", "", {}) == 0.0

    def test_auto_evaluate_good(self, tuner):
        assert tuner.auto_evaluate("p", "hello function impl", {"min_length": 5, "required_keywords": ["hello"]}) >= 0.7

    def test_auto_evaluate_missing_kw(self, tuner):
        assert tuner.auto_evaluate("p", "short", {"min_length": 100, "required_keywords": ["missing"]}) < 0.5

    def test_auto_evaluate_forbidden(self, tuner):
        assert tuner.auto_evaluate("p", "has TODO and FIXME", {"forbidden_patterns": ["TODO", "FIXME"]}) < 1.0

    def test_auto_evaluate_json_valid(self, tuner):
        assert tuner.auto_evaluate("p", '{"k": "v"}', {"expected_format": "json"}) >= 0.9

    def test_auto_evaluate_json_invalid(self, tuner):
        assert tuner.auto_evaluate("p", "not json", {"expected_format": "json"}) < 0.7

    def test_auto_evaluate_markdown(self, tuner):
        assert tuner.auto_evaluate("p", "# Title\n- item", {"expected_format": "markdown"}) >= 0.8

    def test_suggest_rewrite_insufficient(self, tuner):
        tuner.record_feedback("p", "o", "c", 0.3)
        assert tuner.suggest_prompt_rewrite("p") is None

    def test_suggest_rewrite_good_rating(self, tuner):
        for _ in range(5):
            tuner.record_feedback("p", "o", "c", 0.9)
        assert tuner.suggest_prompt_rewrite("p") is None

    def test_suggest_rewrite_with_corrections(self, tuner):
        for i in range(5):
            tuner.record_feedback("p", f"bad_{i}", f"good_{i}", 0.3)
        r = tuner.suggest_prompt_rewrite("p")
        assert r is not None and "p" in r

    def test_apply_rewrite(self, tuner, tmp_path):
        f = tmp_path / "prompt.json"
        f.write_text(json.dumps({"content": "old", "name": "t"}))
        assert tuner.apply_rewrite("p", "new content", f) is True
        d = json.loads(f.read_text())
        assert d["content"] == "new content" and d["name"] == "t"

    def test_apply_rewrite_missing(self, tuner, tmp_path):
        assert tuner.apply_rewrite("p", "x", tmp_path / "nope.json") is False


# ============================================================
# 6. BasePhase Tests
# ============================================================
class TestBasePhase:
    @pytest.fixture
    def ctx(self):
        c = MagicMock()
        c.logger = _mock_logger()
        c.event_publisher = MagicMock()
        c.file_manager = MagicMock()
        return c

    def test_run_not_implemented(self, ctx):
        from backend.agents.auto_agent_phases.base_phase import BasePhase

        with pytest.raises(NotImplementedError):
            asyncio.run(
                BasePhase(ctx).run(
                    project_description="",
                    project_name="",
                    project_root=Path("/tmp"),
                    readme_content="",
                    initial_structure={},
                    generated_files={},
                    file_paths=[],
                )
            )

    def test_concrete_execute(self, ctx, tmp_path):
        from backend.agents.auto_agent_phases.base_phase import BasePhase

        class TP(BasePhase):
            phase_id = "tp"

            async def run(
                self,
                project_description,
                project_name,
                project_root,
                readme_content,
                initial_structure,
                generated_files,
                file_paths,
                **kw,
            ):
                generated_files["t.py"] = "x"
                file_paths.append("t.py")
                return generated_files, initial_structure, file_paths

        f, s, p = asyncio.run(
            TP(ctx).execute(
                project_description="d",
                project_name="p",
                project_root=tmp_path,
                readme_content="",
                initial_structure={},
                generated_files={},
                file_paths=["e.py"],
            )
        )
        assert "t.py" in f and "t.py" in p and "e.py" in p

    def test_execute_publishes_events(self, ctx, tmp_path):
        from backend.agents.auto_agent_phases.base_phase import BasePhase

        class Ok(BasePhase):
            phase_id = "ok"

            async def run(self, **kw):
                return {}, {}, []

        asyncio.run(
            Ok(ctx).execute(
                project_description="",
                project_name="",
                project_root=tmp_path,
                readme_content="",
                initial_structure={},
                generated_files={},
            )
        )
        calls = ctx.event_publisher.publish.call_args_list
        assert calls[0][0][0] == "phase_start"
        assert calls[1][0][0] == "phase_complete"

    def test_execute_wraps_exception(self, ctx, tmp_path):
        from backend.agents.auto_agent_phases.base_phase import BasePhase
        from backend.utils.core.exceptions import PipelinePhaseError

        class Bad(BasePhase):
            phase_id = "bad"

            async def run(self, **kw):
                raise ValueError("boom")

        with pytest.raises(PipelinePhaseError):
            asyncio.run(
                Bad(ctx).execute(
                    project_description="",
                    project_name="",
                    project_root=tmp_path,
                    readme_content="",
                    initial_structure={},
                    generated_files={},
                )
            )

    def test_file_paths_extracted(self, ctx, tmp_path):
        from backend.agents.auto_agent_phases.base_phase import BasePhase

        received = []

        class FP(BasePhase):
            phase_id = "fp"

            async def run(
                self,
                project_description,
                project_name,
                project_root,
                readme_content,
                initial_structure,
                generated_files,
                file_paths,
                **kw,
            ):
                received.extend(file_paths)
                return generated_files, initial_structure, file_paths

        asyncio.run(
            FP(ctx).execute(
                project_description="",
                project_name="",
                project_root=tmp_path,
                readme_content="",
                initial_structure={},
                generated_files={},
                file_paths=["a.py", "b.py"],
            )
        )
        assert received == ["a.py", "b.py"]


# ============================================================
# 7. PhaseGroup Tests
# ============================================================
class TestPhaseGroups:
    def test_sequential(self):
        from backend.agents.auto_agent_phases.phase_groups import PhaseGroup
        from backend.interfaces.iagent_phase import IAgentPhase

        class A(IAgentPhase):
            async def execute(
                self,
                project_description,
                project_name,
                project_root,
                readme_content,
                initial_structure,
                generated_files,
                **kw,
            ):
                generated_files["a.py"] = "a"
                return generated_files, initial_structure, kw.get("file_paths", [])

        class B(IAgentPhase):
            async def execute(
                self,
                project_description,
                project_name,
                project_root,
                readme_content,
                initial_structure,
                generated_files,
                **kw,
            ):
                generated_files["b.py"] = "b"
                return generated_files, initial_structure, kw.get("file_paths", [])

        f, _, _ = asyncio.run(
            PhaseGroup("t", [A(), B()]).execute(
                project_description="",
                project_name="",
                project_root=Path("/tmp"),
                readme_content="",
                initial_structure={},
                generated_files={},
                file_paths=[],
            )
        )
        assert "a.py" in f and "b.py" in f

    def test_parallel_merges(self):
        from backend.agents.auto_agent_phases.phase_groups import PhaseGroup
        from backend.interfaces.iagent_phase import IAgentPhase

        class C(IAgentPhase):
            async def execute(
                self,
                project_description,
                project_name,
                project_root,
                readme_content,
                initial_structure,
                generated_files,
                **kw,
            ):
                generated_files["c.py"] = "c"
                return generated_files, initial_structure, ["c.py"]

        class D(IAgentPhase):
            async def execute(
                self,
                project_description,
                project_name,
                project_root,
                readme_content,
                initial_structure,
                generated_files,
                **kw,
            ):
                generated_files["d.py"] = "d"
                return generated_files, initial_structure, ["d.py"]

        f, _, p = asyncio.run(
            PhaseGroup("t", [C(), D()], parallel=True).execute(
                project_description="",
                project_name="",
                project_root=Path("/tmp"),
                readme_content="",
                initial_structure={},
                generated_files={},
                file_paths=[],
            )
        )
        assert "c.py" in f and "d.py" in f

    def test_parallel_failure(self):
        from backend.agents.auto_agent_phases.phase_groups import PhaseGroup
        from backend.interfaces.iagent_phase import IAgentPhase
        from backend.utils.core.exceptions import ParallelPhaseError

        class Good(IAgentPhase):
            async def execute(self, *a, **kw):
                return {}, {}, []

        class Bad(IAgentPhase):
            async def execute(self, *a, **kw):
                raise RuntimeError("exploded")

        with pytest.raises(ParallelPhaseError):
            asyncio.run(
                PhaseGroup("t", [Good(), Bad()], parallel=True).execute(
                    project_description="",
                    project_name="",
                    project_root=Path("/tmp"),
                    readme_content="",
                    initial_structure={},
                    generated_files={},
                    file_paths=[],
                )
            )

    def test_build_single_phases(self):
        from backend.agents.auto_agent_phases.phase_groups import build_phase_groups
        from backend.interfaces.iagent_phase import IAgentPhase

        class R(IAgentPhase):
            async def execute(self, *a, **kw):
                pass

        groups = build_phase_groups([R(), R()])
        assert len(groups) == 2

    def test_build_detects_parallel(self):
        from backend.agents.auto_agent_phases.phase_groups import build_phase_groups, PhaseGroup
        from backend.interfaces.iagent_phase import IAgentPhase

        SSP = type("SecurityScanPhase", (IAgentPhase,), {"execute": lambda s, *a, **kw: None})
        LCP = type("LicenseCompliancePhase", (IAgentPhase,), {"execute": lambda s, *a, **kw: None})
        Reg = type("RegularPhase", (IAgentPhase,), {"execute": lambda s, *a, **kw: None})

        groups = build_phase_groups([Reg(), SSP(), LCP(), Reg()])
        assert len(groups) == 3
        assert isinstance(groups[1], PhaseGroup) and groups[1].parallel is True


# ============================================================
# 8. WasmSandbox & DockerSandbox Tests
# ============================================================
class TestSandboxes:
    def test_wasm_unavailable(self):
        from backend.utils.core.wasm_sandbox import WasmSandbox

        assert WasmSandbox(runtime="nonexistent_xyz").is_available is False

    def test_wasm_create_destroy(self):
        from backend.utils.core.wasm_sandbox import WasmSandbox

        sb = WasmSandbox(runtime="nonexistent_xyz")
        inst = sb.create_sandbox()
        assert inst.work_dir.exists()
        sb.destroy_sandbox(inst)
        assert not inst.work_dir.exists()

    def test_wasm_destroy_all(self):
        from backend.utils.core.wasm_sandbox import WasmSandbox

        sb = WasmSandbox(runtime="nonexistent_xyz")
        sb.create_sandbox()
        sb.create_sandbox()
        assert len(sb._instances) == 2
        sb.destroy_all()
        assert len(sb._instances) == 0

    def test_sandbox_instance_to_dict(self):
        from backend.utils.core.wasm_sandbox import WasmSandbox

        sb = WasmSandbox(runtime="nonexistent_xyz")
        inst = sb.create_sandbox(memory_limit_mb=512)
        d = inst.to_dict()
        assert d["memory_limit_mb"] == 512
        sb.destroy_sandbox(inst)

    def test_test_result_to_dict_truncates(self):
        from backend.utils.core.wasm_sandbox import TestResult

        r = TestResult(
            success=True,
            exit_code=0,
            stdout="x" * 10000,
            stderr="y" * 5000,
            duration_seconds=1.2345,
            tests_run=5,
            tests_passed=4,
            tests_failed=1,
        )
        d = r.to_dict()
        assert len(d["stdout"]) <= 5000 and len(d["stderr"]) <= 2000
        assert d["tests_passed"] == 4

    @patch("subprocess.run")
    def test_docker_available(self, mock_run):
        from backend.utils.core.wasm_sandbox import DockerSandbox

        mock_run.return_value = MagicMock(returncode=0)
        assert DockerSandbox(logger=_mock_logger()).is_available is True

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_docker_unavailable(self, mock_run):
        from backend.utils.core.wasm_sandbox import DockerSandbox

        assert DockerSandbox(logger=_mock_logger()).is_available is False

    def test_docker_execute_unavailable_raises(self):
        from backend.utils.core.wasm_sandbox import DockerSandbox
        from backend.utils.core.exceptions import SandboxUnavailableError

        with patch("subprocess.run", side_effect=FileNotFoundError):
            sb = DockerSandbox(logger=_mock_logger())
        with pytest.raises(SandboxUnavailableError):
            sb.execute_in_container("echo hi", work_dir=Path("/tmp"))

    @patch("subprocess.run")
    def test_docker_cleanup(self, mock_run):
        from backend.utils.core.wasm_sandbox import DockerSandbox

        mock_run.side_effect = [
            MagicMock(returncode=0),  # docker info
            MagicMock(returncode=0, stdout="ollash_sandbox_abc\n"),
            MagicMock(returncode=0),
        ]
        sb = DockerSandbox(logger=_mock_logger())
        assert sb.cleanup_orphaned_containers() == 1


# ============================================================
# 9. CommandExecutor async_execute Tests
# ============================================================
class TestCommandExecutorAsync:
    def test_async_simple(self):
        from backend.utils.core.command_executor import CommandExecutor, SandboxLevel

        r = asyncio.run(
            CommandExecutor(sandbox=SandboxLevel.NONE, logger=_mock_logger()).async_execute("python -c \"print('hi')\"")
        )
        assert r.success is True and "hi" in r.stdout

    def test_async_not_found(self):
        from backend.utils.core.command_executor import CommandExecutor, SandboxLevel

        r = asyncio.run(
            CommandExecutor(sandbox=SandboxLevel.NONE, logger=_mock_logger()).async_execute("nonexistent_cmd_xyz")
        )
        assert r.success is False

    def test_async_timeout(self):
        from backend.utils.core.command_executor import CommandExecutor, SandboxLevel

        r = asyncio.run(
            CommandExecutor(sandbox=SandboxLevel.NONE, logger=_mock_logger()).async_execute(
                'python -c "import time; time.sleep(10)"', timeout=1
            )
        )
        assert r.success is False

    def test_async_list_command(self):
        from backend.utils.core.command_executor import CommandExecutor, SandboxLevel

        r = asyncio.run(
            CommandExecutor(sandbox=SandboxLevel.NONE, logger=_mock_logger()).async_execute(
                ["python", "-c", "print('list')"]
            )
        )
        assert r.success is True and "list" in r.stdout


# ============================================================
# 10. ImageAnalyzer Tests
# ============================================================
class TestImageAnalyzer:
    @pytest.fixture
    def analyzer(self):
        from backend.utils.domains.multimedia.image_analyzer import ImageAnalyzer

        vc = MagicMock()
        vc.chat.return_value = {"message": {"content": "Found: button and field."}}
        return ImageAnalyzer(vision_client=vc, logger=_mock_logger())

    @pytest.fixture
    def png(self, tmp_path):
        return _make_png(tmp_path / "test.png")

    def test_load_valid(self, analyzer, png):
        import base64

        r = analyzer._load_image_base64(png)
        assert r is not None
        assert base64.b64decode(r)[:4] == b"\x89PNG"

    def test_load_nonexistent(self, analyzer):
        assert analyzer._load_image_base64(Path("/no/img.png")) is None

    def test_load_bad_ext(self, analyzer, tmp_path):
        f = tmp_path / "test.xyz"
        f.write_text("x")
        assert analyzer._load_image_base64(f) is None

    def test_extract_list_items(self):
        from backend.utils.domains.multimedia.image_analyzer import ImageAnalyzer

        items = ImageAnalyzer._extract_list_items("- DB\n* API\n1. LB", "c")
        assert "DB" in items and "API" in items and "LB" in items

    def test_analyze_screenshot(self, analyzer, png):
        r = asyncio.run(analyzer.analyze_screenshot(png, "errors?"))
        assert "Found" in r

    def test_analyze_diagram(self, analyzer, png):
        r = asyncio.run(analyzer.analyze_diagram(png))
        assert "description" in r

    def test_extract_text(self, analyzer, png):
        analyzer.vision_client.chat.return_value = {"message": {"content": "ERROR: conn refused"}}
        assert "ERROR" in asyncio.run(analyzer.extract_text_from_image(png))

    def test_missing_image(self, analyzer):
        assert "Error" in asyncio.run(analyzer.analyze_screenshot(Path("/no/img.png")))


# ============================================================
# 11. MultiProviderManager Tests
# ============================================================
class TestMultiProviderManager:
    @pytest.fixture
    def manager(self):
        from backend.services.multi_provider_manager import MultiProviderManager

        cfg = MagicMock()
        cfg.ollama_url = "http://localhost:11434"
        cfg.default_model = "llama3.2"
        cfg.default_timeout = 300
        cfg.embedding = "nomic-embed-text"
        cfg.agent_roles = {"coder": "deepseek-coder"}
        ts = MagicMock()
        ts.model_dump.return_value = {}
        return MultiProviderManager(cfg, ts, _mock_logger())

    def test_default_ollama_registered(self, manager):
        assert "ollama" in manager._providers

    def test_register_openai_compat(self, manager):
        from backend.services.multi_provider_manager import ProviderConfig

        manager.register_provider(
            ProviderConfig(
                name="groq",
                provider_type="openai_compatible",
                base_url="https://api.groq.com/openai",
                api_key="k",
                models={"reviewer": "llama-70b"},
            )
        )
        assert "groq" in manager._providers
        assert manager._role_provider_map.get("reviewer") == "groq"

    def test_register_ollama_provider(self, manager):
        from backend.services.multi_provider_manager import ProviderConfig

        manager.register_provider(
            ProviderConfig(
                name="remote", provider_type="ollama", base_url="http://remote:11434", models={"default": "llama3.2"}
            )
        )
        assert "remote" in manager._providers

    def test_available_providers(self, manager):
        p = manager.get_available_providers()
        assert len(p) >= 1 and p[0]["name"] == "ollama"

    def test_provider_config(self):
        from backend.services.multi_provider_manager import ProviderConfig

        pc = ProviderConfig(
            name="t", provider_type="openai_compatible", base_url="http://x", api_key="k", models={"a": "m"}, timeout=60
        )
        assert pc.name == "t" and pc.timeout == 60

    def test_unknown_type_ignored(self, manager):
        from backend.services.multi_provider_manager import ProviderConfig

        manager.register_provider(ProviderConfig(name="bad", provider_type="unknown"))
        assert "bad" not in manager._providers
