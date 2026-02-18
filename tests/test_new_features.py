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
        # shadow_evaluate is published between start and complete
        assert calls[1][0][0] == "shadow_evaluate"
        assert calls[2][0][0] == "phase_complete"

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


# ============================================================
# Benchmark Rubrics Tests
# ============================================================
class TestRubricEvaluator:
    """Tests for multidimensional rubric evaluation system."""

    def test_json_compliance_valid_json(self):
        from backend.utils.core.benchmark_rubrics import RubricDimension, RubricEvaluator

        evaluator = RubricEvaluator(logger=_mock_logger())
        response = '```json\n{"name": "test", "version": "1.0"}\n```'
        result = evaluator.evaluate(
            model_name="test-model",
            task_name="test-task",
            response_content=response,
            task_data={"type": "web_app"},
            duration_sec=10.0,
            dimensions=[RubricDimension.STRICT_JSON],
        )
        json_dim = result.dimension_results[0]
        assert json_dim.score == 1.0  # All blocks are valid
        assert json_dim.raw_data["valid_blocks"] >= 1

    def test_json_compliance_malformed_json(self):
        from backend.utils.core.benchmark_rubrics import RubricDimension, RubricEvaluator

        evaluator = RubricEvaluator(logger=_mock_logger())
        # Only use code blocks to avoid standalone regex double-counting
        response = '```json\n{invalid json here}\n```\n```json\n{"valid": true}\n```'
        result = evaluator.evaluate(
            model_name="test-model",
            task_name="test-task",
            response_content=response,
            task_data={},
            duration_sec=5.0,
            dimensions=[RubricDimension.STRICT_JSON],
        )
        json_dim = result.dimension_results[0]
        assert json_dim.score == 0.5  # Half valid
        assert json_dim.raw_data["total_blocks"] >= 2

    def test_json_compliance_no_json_blocks(self):
        from backend.utils.core.benchmark_rubrics import RubricDimension, RubricEvaluator

        evaluator = RubricEvaluator(logger=_mock_logger())
        result = evaluator.evaluate(
            model_name="m",
            task_name="t",
            response_content="No JSON here, just text.",
            task_data={},
            duration_sec=1.0,
            dimensions=[RubricDimension.STRICT_JSON],
        )
        assert result.dimension_results[0].score == 0.5  # Neutral

    def test_reasoning_depth_with_dependency_ordering(self):
        from backend.utils.core.benchmark_rubrics import RubricDimension, RubricEvaluator

        evaluator = RubricEvaluator(logger=_mock_logger())
        response = (
            "## Plan\n"
            "1. First, resolve the circular dependency between auth and database\n"
            "2. Then, create an interface abstraction to decouple modules\n"
            "3. Finally, use topological sort to determine build order\n"
            "Because auth depends on database, we need to break the cycle.\n"
            "Therefore, we'll use dependency injection to resolve this."
        )
        result = evaluator.evaluate(
            model_name="m",
            task_name="t",
            response_content=response,
            task_data={},
            duration_sec=5.0,
            dimensions=[RubricDimension.REASONING_DEPTH],
        )
        score = result.dimension_results[0].score
        assert score > 0.5, f"Expected high reasoning depth, got {score}"

    def test_reasoning_depth_minimal_response(self):
        from backend.utils.core.benchmark_rubrics import RubricDimension, RubricEvaluator

        evaluator = RubricEvaluator(logger=_mock_logger())
        result = evaluator.evaluate(
            model_name="m",
            task_name="t",
            response_content="Here is the code.",
            task_data={},
            duration_sec=1.0,
            dimensions=[RubricDimension.REASONING_DEPTH],
        )
        assert result.dimension_results[0].score < 0.3

    def test_context_utilization_with_ground_truth(self):
        from backend.utils.core.benchmark_rubrics import RubricDimension, RubricEvaluator

        evaluator = RubricEvaluator(logger=_mock_logger())
        ground_truth = "The application uses Flask with SQLAlchemy for database access"
        response = "This application uses Flask framework with SQLAlchemy ORM for database access and management"
        result = evaluator.evaluate(
            model_name="m",
            task_name="t",
            response_content=response,
            task_data={"ground_truth_summary": ground_truth},
            duration_sec=2.0,
            dimensions=[RubricDimension.CONTEXT_UTILIZATION],
        )
        score = result.dimension_results[0].score
        assert score > 0.3, f"Expected decent context utilization, got {score}"
        assert result.dimension_results[0].raw_data["has_ground_truth"] is True

    def test_context_utilization_no_ground_truth(self):
        from backend.utils.core.benchmark_rubrics import RubricDimension, RubricEvaluator

        evaluator = RubricEvaluator(logger=_mock_logger())
        result = evaluator.evaluate(
            model_name="m",
            task_name="t",
            response_content="A detailed response with many words about the project structure and implementation.",
            task_data={"description": "Build a web app"},
            duration_sec=2.0,
            dimensions=[RubricDimension.CONTEXT_UTILIZATION],
        )
        assert result.dimension_results[0].raw_data["has_ground_truth"] is False

    def test_speed_score_fast_response(self):
        from backend.utils.core.benchmark_rubrics import RubricDimension, RubricEvaluator

        evaluator = RubricEvaluator(logger=_mock_logger())
        result = evaluator.evaluate(
            model_name="m",
            task_name="t",
            response_content="output",
            task_data={"time_limit_minutes": 5},
            duration_sec=30.0,  # 30s out of 300s limit = 10% used
            dimensions=[RubricDimension.SPEED],
        )
        assert result.dimension_results[0].score == pytest.approx(0.9, abs=0.01)

    def test_speed_score_slow_response(self):
        from backend.utils.core.benchmark_rubrics import RubricDimension, RubricEvaluator

        evaluator = RubricEvaluator(logger=_mock_logger())
        result = evaluator.evaluate(
            model_name="m",
            task_name="t",
            response_content="output",
            task_data={"time_limit_minutes": 5},
            duration_sec=270.0,  # 270s out of 300s = 90% used
            dimensions=[RubricDimension.SPEED],
        )
        assert result.dimension_results[0].score == pytest.approx(0.1, abs=0.01)

    def test_evaluate_all_dimensions(self):
        from backend.utils.core.benchmark_rubrics import RubricEvaluator

        evaluator = RubricEvaluator(logger=_mock_logger())
        result = evaluator.evaluate(
            model_name="test-model",
            task_name="test-task",
            response_content='```json\n{"key": "value"}\n```\nStep 1: plan\nStep 2: implement',
            task_data={"time_limit_minutes": 5, "description": "test"},
            duration_sec=60.0,
            dimensions=None,  # All dimensions
        )
        assert len(result.dimension_results) == 5
        assert 0.0 <= result.overall_score <= 1.0

    def test_multidimensional_rubric_phase_mapping(self):
        from backend.utils.core.benchmark_rubrics import MultidimensionalRubric, RubricDimension

        dims = MultidimensionalRubric.get_dimensions_for_task("structure_generation")
        assert RubricDimension.STRICT_JSON in dims
        assert RubricDimension.REASONING_DEPTH in dims

        # Unknown task type returns all dimensions
        all_dims = MultidimensionalRubric.get_dimensions_for_task("nonexistent_type")
        assert len(all_dims) == 5


# ============================================================
# Affinity Matrix Tests
# ============================================================
class TestAffinityMatrix:
    """Tests for Phase-Model affinity matrix."""

    @pytest.fixture
    def affinity_setup(self, tmp_path):
        import datetime

        bench_dir = tmp_path / "bench"
        bench_dir.mkdir()
        results = [
            {
                "model_name": "model-a",
                "task_type": "coder",
                "phase_name": "LogicPlanningPhase",
                "success_rate": 0.9,
                "quality_score": 8.5,
                "avg_tokens": 500,
                "avg_time_ms": 5000,
            },
            {
                "model_name": "model-b",
                "task_type": "coder",
                "phase_name": "LogicPlanningPhase",
                "success_rate": 0.7,
                "quality_score": 6.0,
                "avg_tokens": 300,
                "avg_time_ms": 3000,
            },
        ]
        for i, r in enumerate(results):
            r["timestamp"] = datetime.datetime.now().isoformat()
            with open(bench_dir / f"r_{i}.json", "w") as f:
                json.dump(r, f)
        return bench_dir

    def test_build_matrix_from_benchmark_data(self, affinity_setup):
        from backend.utils.core.benchmark_model_selector import AffinityMatrix, BenchmarkDatabase

        db = BenchmarkDatabase(affinity_setup, _mock_logger())
        matrix = AffinityMatrix(db, _mock_logger())
        matrix.build()
        data = matrix.to_dict()
        assert "LogicPlanningPhase" in data
        assert "model-a" in data["LogicPlanningPhase"]

    def test_get_best_model_for_phase(self, affinity_setup):
        from backend.utils.core.benchmark_model_selector import AffinityMatrix, BenchmarkDatabase

        db = BenchmarkDatabase(affinity_setup, _mock_logger())
        matrix = AffinityMatrix(db, _mock_logger())
        matrix.build()
        best = matrix.get_best_model_for_phase("LogicPlanningPhase")
        assert best == "model-a"  # Higher success rate

    def test_get_affinity_missing_pair(self, affinity_setup):
        from backend.utils.core.benchmark_model_selector import AffinityMatrix, BenchmarkDatabase

        db = BenchmarkDatabase(affinity_setup, _mock_logger())
        matrix = AffinityMatrix(db, _mock_logger())
        matrix.build()
        assert matrix.get_affinity("NonexistentPhase", "model-a") == 0.0

    def test_to_dict_serialization(self, affinity_setup):
        from backend.utils.core.benchmark_model_selector import AffinityMatrix, BenchmarkDatabase

        db = BenchmarkDatabase(affinity_setup, _mock_logger())
        matrix = AffinityMatrix(db, _mock_logger())
        matrix.build()
        d = matrix.to_dict()
        assert isinstance(d, dict)
        for phase_models in d.values():
            for score in phase_models.values():
                assert isinstance(score, float)


# ============================================================
# Cost Efficiency Calculator Tests
# ============================================================
class TestCostEfficiencyCalculator:
    """Tests for cost-efficiency ratio calculations."""

    def test_small_fast_model_high_efficiency(self):
        from backend.utils.core.benchmark_model_selector import CostEfficiencyCalculator

        sizes = {"small-model": 5 * 1_073_741_824}  # 5GB = small tier
        calc = CostEfficiencyCalculator(sizes, _mock_logger())
        eff = calc.compute_efficiency("small-model", quality_score=8.0, avg_time_ms=1000, max_time_ms=10000)
        assert eff > 10.0  # High efficiency: good quality, small, fast

    def test_large_slow_model_low_efficiency(self):
        from backend.utils.core.benchmark_model_selector import CostEfficiencyCalculator

        sizes = {"large-model": 80 * 1_073_741_824}  # 80GB = xlarge tier
        calc = CostEfficiencyCalculator(sizes, _mock_logger())
        eff = calc.compute_efficiency("large-model", quality_score=8.0, avg_time_ms=9000, max_time_ms=10000)
        assert eff < 5.0  # Low efficiency: same quality but huge and slow

    def test_rank_models_by_efficiency(self):
        import datetime

        from backend.utils.core.benchmark_model_selector import BenchmarkDatabase, CostEfficiencyCalculator

        # Create in-memory benchmark data
        logger = _mock_logger()
        sizes = {
            "fast-small": 3 * 1_073_741_824,
            "slow-large": 50 * 1_073_741_824,
        }
        calc = CostEfficiencyCalculator(sizes, logger)

        # Create temp benchmark dir
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            bench_dir = Path(td)
            results = [
                {
                    "model_name": "fast-small",
                    "task_type": "coder",
                    "success_rate": 0.8,
                    "quality_score": 7.0,
                    "avg_tokens": 300,
                    "avg_time_ms": 2000,
                    "timestamp": datetime.datetime.now().isoformat(),
                },
                {
                    "model_name": "slow-large",
                    "task_type": "coder",
                    "success_rate": 0.9,
                    "quality_score": 8.0,
                    "avg_tokens": 500,
                    "avg_time_ms": 8000,
                    "timestamp": datetime.datetime.now().isoformat(),
                },
            ]
            for i, r in enumerate(results):
                with open(bench_dir / f"r_{i}.json", "w") as f:
                    json.dump(r, f)

            db = BenchmarkDatabase(bench_dir, logger)
            rankings = calc.rank_models_by_efficiency(db, "coder")

        assert len(rankings) == 2
        # fast-small should rank higher due to size/speed advantage
        assert rankings[0][0] == "fast-small"

    def test_equal_quality_different_sizes(self):
        from backend.utils.core.benchmark_model_selector import CostEfficiencyCalculator

        sizes = {
            "small": 5 * 1_073_741_824,
            "large": 50 * 1_073_741_824,
        }
        calc = CostEfficiencyCalculator(sizes, _mock_logger())
        small_eff = calc.compute_efficiency("small", 8.0, 5000, 10000)
        large_eff = calc.compute_efficiency("large", 8.0, 5000, 10000)
        assert small_eff > large_eff  # Same quality/speed, smaller model wins


# ============================================================
# Weighted Phase Loss Tests
# ============================================================
class TestWeightedPhaseLoss:
    """Tests for the weighted phase loss function."""

    def test_critical_phase_higher_weight(self):
        from backend.utils.core.benchmark_model_selector import BenchmarkDatabase

        logger = _mock_logger()
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            db = BenchmarkDatabase(Path(td), logger)

        # Scenario: model fails on SeniorReview (weight=3.0) but aces Readme (weight=0.5)
        phase_results = {
            "SeniorReviewPhase": 0.2,  # Bad
            "ReadmeGenerationPhase": 1.0,  # Perfect
        }
        loss = db.weighted_phase_loss("model-x", phase_results)
        # Loss should be dominated by SeniorReview failure
        assert loss > 0.5, f"Loss should be high due to SeniorReview failure, got {loss}"

    def test_zero_loss_perfect_scores(self):
        from backend.utils.core.benchmark_model_selector import BenchmarkDatabase

        logger = _mock_logger()
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            db = BenchmarkDatabase(Path(td), logger)

        phase_results = {
            "SeniorReviewPhase": 1.0,
            "LogicPlanningPhase": 1.0,
            "ReadmeGenerationPhase": 1.0,
        }
        loss = db.weighted_phase_loss("model-x", phase_results)
        assert loss == pytest.approx(0.0)

    def test_custom_weights(self):
        from backend.utils.core.benchmark_model_selector import BenchmarkDatabase

        logger = _mock_logger()
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            db = BenchmarkDatabase(Path(td), logger)

        custom_weights = {"PhaseA": 10.0, "PhaseB": 1.0}
        results = {"PhaseA": 0.0, "PhaseB": 1.0}
        loss = db.weighted_phase_loss("m", results, phase_weights=custom_weights)
        # PhaseA has weight 10, score 0 -> loss contribution = 10
        # PhaseB has weight 1, score 1 -> loss contribution = 0
        # Total = 10/11 ≈ 0.909
        assert loss == pytest.approx(10.0 / 11.0, abs=0.01)


# ============================================================
# Shadow Evaluator Tests
# ============================================================
class TestShadowEvaluator:
    """Tests for the shadow evaluation system."""

    @pytest.fixture
    def mock_publisher(self):
        pub = MagicMock()
        pub.subscribe = MagicMock()
        pub.unsubscribe = MagicMock()
        return pub

    def test_start_subscribes_to_events(self, mock_publisher, tmp_path):
        from backend.utils.core.shadow_evaluator import ShadowEvaluator

        evaluator = ShadowEvaluator(logger=_mock_logger(), event_publisher=mock_publisher, log_dir=tmp_path)
        evaluator.start()
        assert mock_publisher.subscribe.call_count == 2
        assert evaluator._active is True

    def test_stop_unsubscribes_and_persists(self, mock_publisher, tmp_path):
        from backend.utils.core.shadow_evaluator import ShadowEvaluator, ShadowLog

        evaluator = ShadowEvaluator(logger=_mock_logger(), event_publisher=mock_publisher, log_dir=tmp_path)
        evaluator.start()
        evaluator.record_shadow_log(
            ShadowLog(
                timestamp=1.0,
                phase_name="TestPhase",
                model_name="m",
                input_hash="abc",
                output_preview="test",
            )
        )
        evaluator.stop()
        assert mock_publisher.unsubscribe.call_count == 2
        assert evaluator._active is False
        # Check file was persisted
        import glob as globmod

        log_files = globmod.glob(str(tmp_path / "shadow_logs_*.json"))
        assert len(log_files) == 1

    def test_record_shadow_log(self, mock_publisher, tmp_path):
        from backend.utils.core.shadow_evaluator import ShadowEvaluator, ShadowLog

        evaluator = ShadowEvaluator(logger=_mock_logger(), event_publisher=mock_publisher, log_dir=tmp_path)
        log = ShadowLog(
            timestamp=1.0,
            phase_name="P1",
            model_name="model-a",
            input_hash="h1",
            output_preview="output",
        )
        evaluator.record_shadow_log(log)
        assert len(evaluator._logs) == 1

    def test_correction_rate_calculation(self, mock_publisher, tmp_path):
        from backend.utils.core.shadow_evaluator import ShadowEvaluator, ShadowLog

        evaluator = ShadowEvaluator(logger=_mock_logger(), event_publisher=mock_publisher, log_dir=tmp_path)
        # 2 logs: 1 with correction, 1 without
        evaluator.record_shadow_log(
            ShadowLog(
                timestamp=1.0,
                phase_name="P1",
                model_name="model-a",
                input_hash="h1",
                output_preview="out1",
                critic_correction="fix this",
            )
        )
        evaluator.record_shadow_log(
            ShadowLog(
                timestamp=2.0,
                phase_name="P1",
                model_name="model-a",
                input_hash="h2",
                output_preview="out2",
            )
        )
        rate = evaluator.get_correction_rate("model-a")
        assert rate == pytest.approx(0.5)

    def test_correction_rate_above_threshold(self, mock_publisher, tmp_path):
        from backend.utils.core.shadow_evaluator import ShadowEvaluator, ShadowLog

        evaluator = ShadowEvaluator(
            logger=_mock_logger(),
            event_publisher=mock_publisher,
            log_dir=tmp_path,
            critic_threshold=0.3,
        )
        # All corrected
        for i in range(5):
            evaluator.record_shadow_log(
                ShadowLog(
                    timestamp=float(i),
                    phase_name="P1",
                    model_name="bad-model",
                    input_hash=f"h{i}",
                    output_preview=f"out{i}",
                    critic_correction="rewrite needed",
                )
            )
        assert evaluator.is_model_flagged("bad-model") is True
        assert evaluator.is_model_flagged("other-model") is False

    def test_performance_report_generation(self, mock_publisher, tmp_path):
        from backend.utils.core.shadow_evaluator import ShadowEvaluator, ShadowLog

        evaluator = ShadowEvaluator(logger=_mock_logger(), event_publisher=mock_publisher, log_dir=tmp_path)
        evaluator.record_shadow_log(
            ShadowLog(
                timestamp=1.0,
                phase_name="P1",
                model_name="m1",
                input_hash="h1",
                output_preview="out",
                critic_correction="fix",
                correction_severity=0.5,
            )
        )
        evaluator.record_shadow_log(
            ShadowLog(
                timestamp=2.0,
                phase_name="P2",
                model_name="m1",
                input_hash="h2",
                output_preview="out",
            )
        )
        report = evaluator.get_performance_report()
        assert report["total_logs"] == 2
        assert "m1" in report["models"]
        assert report["models"]["m1"]["total_evaluations"] == 2
        assert report["models"]["m1"]["corrections"] == 1
        assert report["models"]["m1"]["correction_rate"] == pytest.approx(0.5)


# ============================================================
# Phase Failure Database Tests
# ============================================================
class TestPhaseFailureDatabase:
    """Tests for the phase failure tracking database."""

    def test_record_failure(self, tmp_path):
        from backend.utils.core.phase_failure_db import PhaseFailureDatabase, PhaseFailureRecord

        db = PhaseFailureDatabase(db_dir=tmp_path, logger=_mock_logger())
        db.record_failure(
            PhaseFailureRecord(
                model_name="model-a",
                phase_name="SeniorReviewPhase",
                failure_type="exception",
                timestamp=1.0,
                details="timeout",
            )
        )
        assert db.get_failure_count("model-a", "SeniorReviewPhase") == 1

    def test_model_becomes_unsuitable_after_threshold(self, tmp_path):
        from backend.utils.core.phase_failure_db import PhaseFailureDatabase, PhaseFailureRecord

        db = PhaseFailureDatabase(db_dir=tmp_path, logger=_mock_logger(), unsuitability_threshold=3)
        for i in range(3):
            db.record_failure(
                PhaseFailureRecord(
                    model_name="bad-model",
                    phase_name="LogicPlanningPhase",
                    failure_type="loop_detected",
                    timestamp=float(i),
                )
            )
        assert db.is_model_suitable("bad-model", "LogicPlanningPhase") is False
        assert db.is_model_suitable("good-model", "LogicPlanningPhase") is True

    def test_is_model_suitable_true(self, tmp_path):
        from backend.utils.core.phase_failure_db import PhaseFailureDatabase

        db = PhaseFailureDatabase(db_dir=tmp_path, logger=_mock_logger())
        assert db.is_model_suitable("any-model", "AnyPhase") is True

    def test_is_model_suitable_false(self, tmp_path):
        from backend.utils.core.phase_failure_db import PhaseFailureDatabase, PhaseFailureRecord

        db = PhaseFailureDatabase(db_dir=tmp_path, logger=_mock_logger(), unsuitability_threshold=2)
        for i in range(2):
            db.record_failure(
                PhaseFailureRecord(
                    model_name="m1",
                    phase_name="P1",
                    failure_type="timeout",
                    timestamp=float(i),
                )
            )
        assert db.is_model_suitable("m1", "P1") is False

    def test_load_and_save_persistence(self, tmp_path):
        from backend.utils.core.phase_failure_db import PhaseFailureDatabase, PhaseFailureRecord

        # Create DB, add records, let it save
        db1 = PhaseFailureDatabase(db_dir=tmp_path, logger=_mock_logger(), unsuitability_threshold=2)
        db1.record_failure(
            PhaseFailureRecord(
                model_name="m1",
                phase_name="P1",
                failure_type="exception",
                timestamp=1.0,
            )
        )
        db1.record_failure(
            PhaseFailureRecord(
                model_name="m1",
                phase_name="P1",
                failure_type="exception",
                timestamp=2.0,
            )
        )
        # Create new DB instance from same dir - should load persisted data
        db2 = PhaseFailureDatabase(db_dir=tmp_path, logger=_mock_logger(), unsuitability_threshold=2)
        assert db2.get_failure_count("m1", "P1") == 2
        assert db2.is_model_suitable("m1", "P1") is False

    def test_failure_summary(self, tmp_path):
        from backend.utils.core.phase_failure_db import PhaseFailureDatabase, PhaseFailureRecord

        db = PhaseFailureDatabase(db_dir=tmp_path, logger=_mock_logger())
        db.record_failure(
            PhaseFailureRecord(
                model_name="m1",
                phase_name="P1",
                failure_type="exception",
                timestamp=1.0,
            )
        )
        db.record_failure(
            PhaseFailureRecord(
                model_name="m2",
                phase_name="P1",
                failure_type="loop_detected",
                timestamp=2.0,
            )
        )
        summary = db.get_failure_summary()
        assert summary["total_failures"] == 2
        assert "P1" in summary["phases"]
        assert "m1" in summary["phases"]["P1"]
        assert "m2" in summary["phases"]["P1"]


# ============================================================
# Benchmark Validation Tests
# ============================================================
class TestBenchmarkValidation:
    """Tests for dependency hallucination and refactoring validation."""

    def test_dependency_hallucination_all_valid(self):
        from backend.agents.auto_benchmarker import ModelBenchmarker

        benchmarker = ModelBenchmarker.__new__(ModelBenchmarker)
        benchmarker.logger = _mock_logger()
        response = "```text\nflask==2.3.0\nrequests==2.31.0\nnumpy==1.24.0\n```"
        result = benchmarker._validate_dependency_hallucination(response)
        assert result["total_packages"] == 3
        assert result["hallucination_rate"] == 0.0
        assert len(result["hallucinated_packages"]) == 0

    def test_dependency_hallucination_with_fake_packages(self):
        from backend.agents.auto_benchmarker import ModelBenchmarker

        benchmarker = ModelBenchmarker.__new__(ModelBenchmarker)
        benchmarker.logger = _mock_logger()
        response = "```text\nflask==2.3.0\nfake_nonexistent_pkg==1.0\nmagic_unicorn_lib==3.0\n```"
        result = benchmarker._validate_dependency_hallucination(response)
        assert result["total_packages"] == 3
        assert result["verified_packages"] == 1
        assert len(result["hallucinated_packages"]) == 2
        assert result["hallucination_rate"] == pytest.approx(2 / 3, abs=0.01)

    def test_refactoring_quality_flask_to_fastapi(self):
        from backend.agents.auto_benchmarker import ModelBenchmarker

        benchmarker = ModelBenchmarker.__new__(ModelBenchmarker)
        benchmarker.logger = _mock_logger()
        response = (
            "from fastapi import FastAPI, HTTPException\n"
            "from pydantic import BaseModel\n\n"
            "app = FastAPI()\n\n"
            "@app.get('/api/users')\n"
            "async def list_users():\n"
            "    return []\n\n"
            "@app.post('/api/users')\n"
            "async def create_user():\n"
            "    return {}\n\n"
            "@app.delete('/api/users/{id}')\n"
            "async def delete_user(id: int):\n"
            "    return {}\n"
        )
        result = benchmarker._validate_refactoring_quality(response, "flask", "fastapi")
        assert result["original_removed"] is True
        assert result["target_added"] is True
        assert result["target_route_count"] >= 3
        assert result["refactoring_score"] > 0.5

    def test_refactoring_quality_missing_target_imports(self):
        from backend.agents.auto_benchmarker import ModelBenchmarker

        benchmarker = ModelBenchmarker.__new__(ModelBenchmarker)
        benchmarker.logger = _mock_logger()
        response = "from flask import Flask\napp = Flask(__name__)\n@app.route('/test')\ndef test(): pass"
        result = benchmarker._validate_refactoring_quality(response, "flask", "fastapi")
        assert result["original_removed"] is False  # Flask still present
        assert result["target_added"] is False  # FastAPI not found
        assert result["refactoring_score"] < 0.5


# ============================================================
# Benchmark Config Schema Tests
# ============================================================
class TestBenchmarkConfigSchema:
    """Tests for BenchmarkConfig Pydantic schema."""

    def test_default_benchmark_config(self):
        from backend.core.config_schemas import BenchmarkConfig

        config = BenchmarkConfig()
        assert config.shadow_evaluation_enabled is False
        assert config.shadow_critic_threshold == 0.3
        assert config.phase_failure_threshold == 3
        assert config.cost_efficiency_weight == 0.3
        assert config.rubric_evaluation_enabled is True

    def test_tool_settings_includes_benchmark(self):
        from backend.core.config_schemas import ToolSettingsConfig

        config = ToolSettingsConfig()
        assert hasattr(config, "benchmark")
        assert config.benchmark.shadow_evaluation_enabled is False

    def test_custom_benchmark_config(self):
        from backend.core.config_schemas import BenchmarkConfig

        config = BenchmarkConfig(
            shadow_evaluation_enabled=True,
            shadow_critic_threshold=0.5,
            phase_failure_threshold=5,
            cost_efficiency_weight=0.7,
        )
        assert config.shadow_evaluation_enabled is True
        assert config.shadow_critic_threshold == 0.5
        assert config.phase_failure_threshold == 5


# ============================================================
# Base Phase Shadow Hooks Tests
# ============================================================
class TestBasePhaseHooks:
    """Tests for shadow evaluation and failure hooks in BasePhase."""

    def test_shadow_evaluate_publish_on_success(self):
        from backend.agents.auto_agent_phases.base_phase import BasePhase

        mock_context = MagicMock()
        mock_context.event_publisher = MagicMock()
        mock_context.logger = _mock_logger()

        phase = BasePhase.__new__(BasePhase)
        phase.context = mock_context
        phase.phase_id = "TestPhase"
        phase.phase_label = "Test"

        result = ({"file.py": "content"}, {}, ["file.py"])
        phase._publish_shadow_evaluate(result)

        mock_context.event_publisher.publish.assert_called_once()
        call_args = mock_context.event_publisher.publish.call_args
        assert call_args[0][0] == "shadow_evaluate"

    def test_phase_failure_publish(self):
        from backend.agents.auto_agent_phases.base_phase import BasePhase

        mock_context = MagicMock()
        mock_context.event_publisher = MagicMock()
        mock_context.logger = _mock_logger()

        phase = BasePhase.__new__(BasePhase)
        phase.context = mock_context
        phase.phase_id = "TestPhase"
        phase.phase_label = "Test"

        phase._publish_phase_failure("exception", "some error")

        mock_context.event_publisher.publish.assert_called_once()
        call_args = mock_context.event_publisher.publish.call_args
        assert call_args[0][0] == "phase_failure"

    def test_shadow_hooks_never_raise(self):
        from backend.agents.auto_agent_phases.base_phase import BasePhase

        mock_context = MagicMock()
        mock_context.event_publisher.publish.side_effect = RuntimeError("boom")
        mock_context.logger = _mock_logger()

        phase = BasePhase.__new__(BasePhase)
        phase.context = mock_context
        phase.phase_id = "TestPhase"
        phase.phase_label = "Test"

        # These should not raise despite the RuntimeError
        phase._publish_shadow_evaluate(None)
        phase._publish_phase_failure("exception", "details")
