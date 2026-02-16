"""
Comprehensive unit tests for new features part 1.

Tests:
- MultiAgentOrchestrator
- CheckpointManager
- EpisodicMemory
- VulnerabilityScanner
- RefactoringAnalyzer
"""

import asyncio
import json
import sqlite3
from unittest.mock import AsyncMock, MagicMock


from backend.utils.core.checkpoint_manager import Checkpoint, CheckpointManager, CheckpointStore
from backend.utils.core.episodic_memory import EpisodicEntry, EpisodicMemory
from backend.utils.core.multi_agent_orchestrator import MultiAgentOrchestrator
from backend.utils.core.refactoring_analyzer import RefactoringAnalyzer, SolidViolation
from backend.utils.core.vulnerability_scanner import (
    ScanResult,
    Vulnerability,
    VulnerabilityScanner,
)


# ============================================================================
# TestMultiAgentOrchestrator
# ============================================================================


class TestMultiAgentOrchestrator:
    """Tests for MultiAgentOrchestrator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logger = MagicMock()
        self.agents = [MagicMock(), MagicMock(), MagicMock()]
        self.parallel_gen = MagicMock()
        self.dep_graph = MagicMock()
        self.orchestrator = MultiAgentOrchestrator(
            agents=self.agents,
            parallel_gen=self.parallel_gen,
            dep_graph=self.dep_graph,
            logger=self.logger,
        )

    def test_split_into_groups_empty_list(self):
        """Test split_into_groups with empty file list."""
        result = self.orchestrator.split_into_groups([], {})
        assert result == []

    def test_split_into_groups_single_file(self):
        """Test split_into_groups with a single file."""
        self.dep_graph.get_dependencies.return_value = []
        result = self.orchestrator.split_into_groups(["file1.py"], {})
        assert len(result) == 1
        assert result[0] == ["file1.py"]

    def test_split_into_groups_multiple_independent_files(self):
        """Test split_into_groups with multiple independent files."""
        self.dep_graph.get_dependencies.return_value = []
        files = ["file1.py", "file2.py", "file3.py"]
        result = self.orchestrator.split_into_groups(files, {})

        # Should create groups (may merge to match agent count)
        assert len(result) <= len(self.agents)

        # All files should be present
        all_files = [f for group in result for f in group]
        assert set(all_files) == set(files)

    def test_split_into_groups_with_dependencies(self):
        """Test split_into_groups with files that have dependencies."""

        def get_deps(path):
            if path == "main.py":
                return ["utils.py"]
            elif path == "test.py":
                return ["main.py"]
            return []

        self.dep_graph.get_dependencies.side_effect = get_deps

        files = ["main.py", "utils.py", "test.py", "independent.py"]
        result = self.orchestrator.split_into_groups(files, {})

        # Dependent files should be in same group
        all_files = [f for group in result for f in group]
        assert set(all_files) == set(files)

        # main.py, utils.py, test.py should be together
        found_together = False
        for group in result:
            if "main.py" in group and "utils.py" in group and "test.py" in group:
                found_together = True
        assert found_together

    def test_orchestrate_empty_files(self):
        """Test orchestrate with no files."""
        result = asyncio.run(self.orchestrator.orchestrate([], {}, AsyncMock()))
        assert result == {}

    def test_orchestrate_with_mocked_agents(self):
        """Test orchestrate with mocked agents and generation function."""

        async def mock_gen_fn(agent, file_path, context_files, **kwargs):
            return f"content_of_{file_path}"

        files = ["file1.py", "file2.py"]
        self.dep_graph.get_dependencies.return_value = []

        result = asyncio.run(
            self.orchestrator.orchestrate(
                files,
                {},
                mock_gen_fn,
            )
        )

        assert len(result) == 2
        assert "file1.py" in result
        assert "file2.py" in result
        assert result["file1.py"] == "content_of_file1.py"
        assert result["file2.py"] == "content_of_file2.py"

    def test_orchestrate_exception_handling(self):
        """Test that exceptions in one group don't affect others."""

        async def mock_gen_fn(agent, file_path, context_files, **kwargs):
            if file_path == "bad.py":
                raise ValueError("Generation failed")
            return f"content_of_{file_path}"

        files = ["good1.py", "bad.py", "good2.py"]
        self.dep_graph.get_dependencies.return_value = []

        result = asyncio.run(
            self.orchestrator.orchestrate(
                files,
                {},
                mock_gen_fn,
            )
        )

        # Good files should succeed even if bad.py fails
        assert "good1.py" in result or "good2.py" in result
        assert len(result) >= 1  # At least one file should succeed


# ============================================================================
# TestCheckpointManager
# ============================================================================


class TestCheckpointManager:
    """Tests for CheckpointManager and related classes."""

    def test_checkpoint_to_dict_from_dict_roundtrip(self):
        """Test Checkpoint.to_dict and from_dict roundtrip."""
        checkpoint = Checkpoint(
            project_name="test_project",
            phase_name="structure_generation",
            phase_index=1,
            timestamp="2026-02-16T10:00:00",
            generated_files={"file1.py": "content1"},
            structure={"dirs": ["src"], "files": ["file1.py"]},
            file_paths=["file1.py"],
            readme_content="# Test README",
            logic_plan={"steps": ["step1"]},
            exec_params={"model": "llama3"},
        )

        data = checkpoint.to_dict()
        restored = Checkpoint.from_dict(data)

        assert restored.project_name == checkpoint.project_name
        assert restored.phase_name == checkpoint.phase_name
        assert restored.phase_index == checkpoint.phase_index
        assert restored.generated_files == checkpoint.generated_files
        assert restored.structure == checkpoint.structure
        assert restored.file_paths == checkpoint.file_paths
        assert restored.readme_content == checkpoint.readme_content
        assert restored.logic_plan == checkpoint.logic_plan

    def test_checkpoint_store_init(self, tmp_path):
        """Test CheckpointStore initialization creates database."""
        db_path = tmp_path / "test_index.db"
        store = CheckpointStore(db_path)

        assert db_path.exists()

        # Verify tables exist
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='checkpoints'")
            assert cursor.fetchone() is not None

    def test_checkpoint_store_index_and_query(self, tmp_path):
        """Test CheckpointStore.index_checkpoint and query."""
        db_path = tmp_path / "test_index.db"
        store = CheckpointStore(db_path)

        checkpoint = Checkpoint(
            project_name="test_proj",
            phase_name="phase1",
            phase_index=1,
            timestamp="2026-02-16T10:00:00",
            generated_files={"f1.py": "content"},
            structure={},
            file_paths=["f1.py"],
            readme_content="# README",
        )

        json_path = tmp_path / "checkpoint.json"
        store.index_checkpoint(checkpoint, json_path)

        # Query all
        results = store.query(project_name="test_proj")
        assert len(results) == 1
        assert results[0]["phase_name"] == "phase1"
        assert results[0]["file_count"] == 1

    def test_checkpoint_store_get_latest_phase_index(self, tmp_path):
        """Test CheckpointStore.get_latest_phase_index."""
        db_path = tmp_path / "test_index.db"
        store = CheckpointStore(db_path)

        # Index multiple checkpoints
        for i in range(3):
            checkpoint = Checkpoint(
                project_name="test_proj",
                phase_name=f"phase{i}",
                phase_index=i,
                timestamp="2026-02-16T10:00:00",
                generated_files={},
                structure={},
                file_paths=[],
                readme_content="",
            )
            store.index_checkpoint(checkpoint, tmp_path / f"cp{i}.json")

        latest = store.get_latest_phase_index("test_proj")
        assert latest == 2

    def test_checkpoint_store_delete_project(self, tmp_path):
        """Test CheckpointStore.delete_project."""
        db_path = tmp_path / "test_index.db"
        store = CheckpointStore(db_path)

        checkpoint = Checkpoint(
            project_name="test_proj",
            phase_name="phase1",
            phase_index=1,
            timestamp="2026-02-16T10:00:00",
            generated_files={},
            structure={},
            file_paths=[],
            readme_content="",
        )
        store.index_checkpoint(checkpoint, tmp_path / "cp.json")

        deleted = store.delete_project("test_proj")
        assert deleted == 1

        results = store.query(project_name="test_proj")
        assert len(results) == 0

    def test_checkpoint_manager_save(self, tmp_path):
        """Test CheckpointManager.save creates JSON file and SQLite index."""
        logger = MagicMock()
        manager = CheckpointManager(base_dir=tmp_path, logger=logger)

        json_path = manager.save(
            project_name="my_project",
            phase_name="structure",
            phase_index=1,
            generated_files={"main.py": "print('hello')"},
            structure={"dirs": ["src"]},
            file_paths=["main.py"],
            readme_content="# My Project",
            logic_plan={"steps": []},
            exec_params={"model": "llama3"},
        )

        # Verify JSON file exists
        assert json_path.exists()

        # Verify JSON content
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["project_name"] == "my_project"
        assert data["phase_name"] == "structure"
        assert data["phase_index"] == 1

        # Verify SQLite index
        results = manager.store.query(project_name="my_project")
        assert len(results) == 1
        assert results[0]["phase_name"] == "structure"

    def test_checkpoint_manager_load_latest(self, tmp_path):
        """Test CheckpointManager.load_latest returns most recent checkpoint."""
        logger = MagicMock()
        manager = CheckpointManager(base_dir=tmp_path, logger=logger)

        # Save multiple checkpoints
        for i in range(3):
            manager.save(
                project_name="my_project",
                phase_name=f"phase{i}",
                phase_index=i,
                generated_files={},
                structure={},
                file_paths=[],
                readme_content="",
            )

        latest = manager.load_latest("my_project")
        assert latest is not None
        assert latest.phase_index == 2
        assert latest.phase_name == "phase2"

    def test_checkpoint_manager_load_at_phase(self, tmp_path):
        """Test CheckpointManager.load_at_phase returns specific phase."""
        logger = MagicMock()
        manager = CheckpointManager(base_dir=tmp_path, logger=logger)

        manager.save(
            project_name="my_project",
            phase_name="structure",
            phase_index=1,
            generated_files={"file1.py": "content1"},
            structure={},
            file_paths=[],
            readme_content="",
        )

        manager.save(
            project_name="my_project",
            phase_name="content",
            phase_index=2,
            generated_files={"file2.py": "content2"},
            structure={},
            file_paths=[],
            readme_content="",
        )

        checkpoint = manager.load_at_phase("my_project", "structure")
        assert checkpoint is not None
        assert checkpoint.phase_name == "structure"
        assert checkpoint.phase_index == 1
        assert "file1.py" in checkpoint.generated_files

    def test_checkpoint_manager_list_checkpoints(self, tmp_path):
        """Test CheckpointManager.list_checkpoints returns all for a project."""
        logger = MagicMock()
        manager = CheckpointManager(base_dir=tmp_path, logger=logger)

        for i in range(3):
            manager.save(
                project_name="my_project",
                phase_name=f"phase{i}",
                phase_index=i,
                generated_files={},
                structure={},
                file_paths=[],
                readme_content="",
            )

        checkpoints = manager.list_checkpoints("my_project")
        assert len(checkpoints) == 3
        phase_names = [cp["phase_name"] for cp in checkpoints]
        assert "phase0" in phase_names
        assert "phase1" in phase_names
        assert "phase2" in phase_names


# ============================================================================
# TestEpisodicMemory
# ============================================================================


class TestEpisodicMemory:
    """Tests for EpisodicMemory."""

    def test_episodic_entry_to_dict_from_dict(self):
        """Test EpisodicEntry serialization."""
        entry = EpisodicEntry(
            project_name="test_proj",
            phase_name="test_phase",
            error_type="SyntaxError",
            error_pattern_id="py_syntax_001",
            error_description="Missing colon",
            solution_applied="Added colon at line 10",
            outcome="success",
            language="python",
            file_path="main.py",
        )

        data = entry.to_dict()
        restored = EpisodicEntry.from_dict(data)

        assert restored.project_name == entry.project_name
        assert restored.error_type == entry.error_type
        assert restored.outcome == entry.outcome
        assert restored.language == entry.language

    def test_episodic_memory_init(self, tmp_path):
        """Test EpisodicMemory initialization."""
        logger = MagicMock()
        memory = EpisodicMemory(memory_dir=tmp_path, logger=logger)

        db_path = tmp_path / "episodic_index.db"
        assert db_path.exists()

        # Verify table exists
        with sqlite3.connect(str(db_path)) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='episodes'")
            assert cursor.fetchone() is not None

    def test_record_episode_persists_to_sqlite_and_json(self, tmp_path):
        """Test record_episode persists to both SQLite and JSON."""
        logger = MagicMock()
        memory = EpisodicMemory(memory_dir=tmp_path, logger=logger)

        entry = EpisodicEntry(
            project_name="test_proj",
            phase_name="repair",
            error_type="ImportError",
            error_pattern_id="py_import_001",
            error_description="Module not found",
            solution_applied="Added import statement",
            outcome="success",
            language="python",
            file_path="main.py",
        )

        memory.record_episode(entry)

        # Check SQLite
        with sqlite3.connect(str(tmp_path / "episodic_index.db")) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM episodes")
            assert cursor.fetchone()[0] == 1

        # Check JSON
        json_path = tmp_path / "test_proj" / "episodes.json"
        assert json_path.exists()
        episodes = json.loads(json_path.read_text(encoding="utf-8"))
        assert len(episodes) == 1
        assert episodes[0]["error_type"] == "ImportError"

    def test_query_solutions_filters_by_error_type(self, tmp_path):
        """Test query_solutions filters by error_type."""
        logger = MagicMock()
        memory = EpisodicMemory(memory_dir=tmp_path, logger=logger)

        # Record multiple episodes
        for i, error_type in enumerate(["ImportError", "SyntaxError", "ImportError"]):
            entry = EpisodicEntry(
                project_name=f"proj{i}",
                phase_name="repair",
                error_type=error_type,
                error_pattern_id=f"err_{i}",
                error_description="Test error",
                solution_applied="Fixed it",
                outcome="success",
                language="python",
            )
            memory.record_episode(entry)

        results = memory.query_solutions(error_type="ImportError")
        assert len(results) == 2
        assert all(r.error_type == "ImportError" for r in results)

    def test_query_solutions_filters_by_language(self, tmp_path):
        """Test query_solutions filters by language."""
        logger = MagicMock()
        memory = EpisodicMemory(memory_dir=tmp_path, logger=logger)

        for lang in ["python", "javascript", "python"]:
            entry = EpisodicEntry(
                project_name="proj",
                phase_name="repair",
                error_type="SyntaxError",
                error_pattern_id="err_syntax",
                error_description="Test",
                solution_applied="Fixed",
                outcome="success",
                language=lang,
            )
            memory.record_episode(entry)

        results = memory.query_solutions(error_type="SyntaxError", language="python")
        assert len(results) == 2
        assert all(r.language == "python" for r in results)

    def test_get_best_solution_returns_success_outcomes(self, tmp_path):
        """Test get_best_solution returns success outcomes."""
        logger = MagicMock()
        memory = EpisodicMemory(memory_dir=tmp_path, logger=logger)

        # Record success and failure
        entry1 = EpisodicEntry(
            project_name="proj1",
            phase_name="repair",
            error_type="ImportError",
            error_pattern_id="py_import_001",
            error_description="Test",
            solution_applied="Added import",
            outcome="success",
            language="python",
        )
        memory.record_episode(entry1)

        entry2 = EpisodicEntry(
            project_name="proj2",
            phase_name="repair",
            error_type="ImportError",
            error_pattern_id="py_import_001",
            error_description="Test",
            solution_applied="Tried something else",
            outcome="failure",
            language="python",
        )
        memory.record_episode(entry2)

        best = memory.get_best_solution("py_import_001")
        assert best is not None
        assert best.outcome == "success"
        assert best.solution_applied == "Added import"

    def test_get_success_rate_calculation(self, tmp_path):
        """Test get_success_rate calculation."""
        logger = MagicMock()
        memory = EpisodicMemory(memory_dir=tmp_path, logger=logger)

        # 2 success, 1 failure
        for i, outcome in enumerate(["success", "failure", "success"]):
            entry = EpisodicEntry(
                project_name=f"proj{i}",
                phase_name="repair",
                error_type="ImportError",
                error_pattern_id="py_import_001",
                error_description="Test",
                solution_applied="Fix",
                outcome=outcome,
                language="python",
            )
            memory.record_episode(entry)

        rate = memory.get_success_rate("py_import_001")
        assert rate == 2 / 3  # 2 successes out of 3 total

    def test_get_statistics_aggregation(self, tmp_path):
        """Test get_statistics aggregation."""
        logger = MagicMock()
        memory = EpisodicMemory(memory_dir=tmp_path, logger=logger)

        # Record multiple episodes
        for i in range(5):
            entry = EpisodicEntry(
                project_name=f"proj{i % 2}",  # 2 unique projects
                phase_name="repair",
                error_type="Error",
                error_pattern_id=f"err_{i % 3}",  # 3 unique patterns
                error_description="Test",
                solution_applied="Fix",
                outcome="success" if i < 3 else "failure",
                language="python",
            )
            memory.record_episode(entry)

        stats = memory.get_statistics()
        assert stats["total_episodes"] == 5
        assert stats["successful_solutions"] == 3
        assert stats["success_rate"] == 3 / 5
        assert stats["unique_error_patterns"] == 3
        assert stats["projects_tracked"] == 2


# ============================================================================
# TestVulnerabilityScanner
# ============================================================================


class TestVulnerabilityScanner:
    """Tests for VulnerabilityScanner."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logger = MagicMock()
        self.scanner = VulnerabilityScanner(logger=self.logger)

    def test_scan_file_sql_injection_critical(self):
        """Test scanning Python code with SQL injection (critical)."""
        code = """
import sqlite3

def get_user(user_id):
    conn = sqlite3.connect("db.sqlite")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
    return cursor.fetchone()
"""
        result = self.scanner.scan_file("test.py", code, language="python")

        assert result.file_path == "test.py"
        assert result.language == "python"
        assert len(result.vulnerabilities) > 0

        # Should detect SQL injection
        sql_vuln = [v for v in result.vulnerabilities if v.rule_id.startswith("SEC-001")]
        assert len(sql_vuln) > 0
        assert sql_vuln[0].severity == "critical"

    def test_scan_file_hardcoded_secrets_high(self):
        """Test scanning code with hardcoded secrets (high)."""
        code = """
API_KEY = "sk-1234567890abcdef"
password = "SuperSecret123"
database_url = "postgresql://user:pass@localhost/db"
"""
        result = self.scanner.scan_file("config.py", code, language="python")

        assert len(result.vulnerabilities) > 0

        # Should detect hardcoded secrets
        secret_vulns = [v for v in result.vulnerabilities if v.rule_id == "SEC-003"]
        assert len(secret_vulns) >= 2  # API_KEY and password
        assert all(v.severity == "high" for v in secret_vulns)

    def test_scan_file_command_injection_critical(self):
        """Test scanning code with command injection (critical)."""
        code = """
import os
import subprocess

def run_command(user_input):
    os.system(f"ls {user_input}")
    subprocess.call(f"echo {user_input}", shell=True)
"""
        result = self.scanner.scan_file("runner.py", code, language="python")

        assert len(result.vulnerabilities) > 0

        # Should detect command injection
        cmd_vulns = [v for v in result.vulnerabilities if v.rule_id.startswith("SEC-002")]
        assert len(cmd_vulns) > 0
        assert all(v.severity == "critical" for v in cmd_vulns)

    def test_scan_result_has_critical(self):
        """Test ScanResult.has_critical property."""
        result = ScanResult(file_path="test.py", language="python")
        assert not result.has_critical

        result.vulnerabilities.append(
            Vulnerability(
                severity="high",
                rule_id="TEST-001",
                description="Test",
                line_number=1,
                code_snippet="test",
            )
        )
        assert not result.has_critical

        result.vulnerabilities.append(
            Vulnerability(
                severity="critical",
                rule_id="TEST-002",
                description="Test",
                line_number=2,
                code_snippet="test",
            )
        )
        assert result.has_critical

    def test_scan_result_has_high(self):
        """Test ScanResult.has_high property."""
        result = ScanResult(file_path="test.py", language="python")
        assert not result.has_high

        result.vulnerabilities.append(
            Vulnerability(
                severity="medium",
                rule_id="TEST-001",
                description="Test",
                line_number=1,
                code_snippet="test",
            )
        )
        assert not result.has_high

        result.vulnerabilities.append(
            Vulnerability(
                severity="high",
                rule_id="TEST-002",
                description="Test",
                line_number=2,
                code_snippet="test",
            )
        )
        assert result.has_high

    def test_scan_result_max_severity(self):
        """Test ScanResult.max_severity property."""
        result = ScanResult(file_path="test.py", language="python")
        assert result.max_severity == "info"

        result.vulnerabilities.append(
            Vulnerability(
                severity="low",
                rule_id="TEST-001",
                description="Test",
                line_number=1,
                code_snippet="test",
            )
        )
        assert result.max_severity == "low"

        result.vulnerabilities.append(
            Vulnerability(
                severity="critical",
                rule_id="TEST-002",
                description="Test",
                line_number=2,
                code_snippet="test",
            )
        )
        assert result.max_severity == "critical"

    def test_scan_project_aggregation(self):
        """Test scan_project aggregation."""
        files = {
            "safe.py": "print('hello')",
            "unsafe.py": 'password = "hardcoded123"',
            "very_unsafe.py": 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
        }

        report = self.scanner.scan_project(files, block_on_critical=True)

        assert report.total_files == 3
        assert report.files_scanned == 3
        assert report.total_vulnerabilities > 0
        assert report.critical_count > 0
        assert report.high_count > 0

    def test_scan_project_blocking(self):
        """Test scan_project blocks files with critical vulnerabilities."""
        files = {
            "safe.py": "print('hello')",
            "critical.py": 'os.system(f"rm {user_input}")',
        }

        report = self.scanner.scan_project(files, block_on_critical=True)

        assert "critical.py" in report.blocked_files
        assert "safe.py" not in report.blocked_files

    def test_language_detection_from_extension(self):
        """Test language detection from file extension."""
        code = "console.log('test')"

        result = self.scanner.scan_file("test.js", code)
        assert result.language == "javascript"

        result = self.scanner.scan_file("test.ts", code)
        assert result.language == "typescript"

        result = self.scanner.scan_file("test.py", code)
        assert result.language == "python"


# ============================================================================
# TestRefactoringAnalyzer
# ============================================================================


class TestRefactoringAnalyzer:
    """Tests for RefactoringAnalyzer."""

    def setup_method(self):
        """Set up test fixtures."""
        self.logger = MagicMock()
        self.analyzer = RefactoringAnalyzer(logger=self.logger)

    def test_srp_detection_class_many_methods(self):
        """Test SRP detection for classes with many methods."""
        code = """
class GodObject:
    def method1(self): pass
    def method2(self): pass
    def method3(self): pass
    def method4(self): pass
    def method5(self): pass
    def method6(self): pass
    def method7(self): pass
    def method8(self): pass
    def method9(self): pass
    def method10(self): pass
    def method11(self): pass
    def method12(self): pass
    def method13(self): pass
    def method14(self): pass
    def method15(self): pass
    def method16(self): pass
"""
        violations = self.analyzer.analyze_solid("test.py", code, language="python")

        srp_violations = [v for v in violations if v.principle == "SRP" and "class" in v.description.lower()]
        assert len(srp_violations) > 0
        assert "GodObject" in srp_violations[0].description

    def test_srp_detection_long_function(self):
        """Test SRP detection for long functions."""
        # Generate a function with > 50 lines
        lines = ["def long_function():"]
        for i in range(60):
            lines.append(f"    x{i} = {i}")
        code = "\n".join(lines)

        violations = self.analyzer.analyze_solid("test.py", code, language="python")

        srp_violations = [v for v in violations if v.principle == "SRP" and "function" in v.description.lower()]
        assert len(srp_violations) > 0
        assert "long_function" in srp_violations[0].description

    def test_isp_detection_many_parameters(self):
        """Test ISP detection for functions with many parameters."""
        code = """
def complex_function(param1, param2, param3, param4, param5, param6, param7, param8):
    pass
"""
        violations = self.analyzer.analyze_solid("test.py", code, language="python")

        isp_violations = [v for v in violations if v.principle == "ISP"]
        assert len(isp_violations) > 0
        assert "complex_function" in isp_violations[0].description
        assert "8 parameters" in isp_violations[0].description

    def test_dip_detection_many_imports(self):
        """Test DIP detection for too many imports."""
        # Generate > 20 imports
        imports = [f"import module{i}" for i in range(25)]
        code = "\n".join(imports)

        violations = self.analyzer.analyze_solid("test.py", code, language="python")

        dip_violations = [v for v in violations if v.principle == "DIP"]
        assert len(dip_violations) > 0
        assert "25 concrete imports" in dip_violations[0].description

    def test_javascript_srp_analysis(self):
        """Test JavaScript SRP analysis."""
        # Generate long JS file
        lines = []
        for i in range(350):
            lines.append(f"const var{i} = {i};")
        code = "\n".join(lines)

        violations = self.analyzer.analyze_solid("test.js", code, language="javascript")

        srp_violations = [v for v in violations if v.principle == "SRP"]
        assert len(srp_violations) > 0
        assert "350 lines" in srp_violations[0].description

    def test_javascript_long_function(self):
        """Test JavaScript long function detection."""
        code = """
function longFunction() {
    const x1 = 1;
    const x2 = 2;
    const x3 = 3;
    const x4 = 4;
    const x5 = 5;
    const x6 = 6;
    const x7 = 7;
    const x8 = 8;
    const x9 = 9;
    const x10 = 10;
    const x11 = 11;
    const x12 = 12;
    const x13 = 13;
    const x14 = 14;
    const x15 = 15;
    const x16 = 16;
    const x17 = 17;
    const x18 = 18;
    const x19 = 19;
    const x20 = 20;
    const x21 = 21;
    const x22 = 22;
    const x23 = 23;
    const x24 = 24;
    const x25 = 25;
    const x26 = 26;
    const x27 = 27;
    const x28 = 28;
    const x29 = 29;
    const x30 = 30;
    const x31 = 31;
    const x32 = 32;
    const x33 = 33;
    const x34 = 34;
    const x35 = 35;
    const x36 = 36;
    const x37 = 37;
    const x38 = 38;
    const x39 = 39;
    const x40 = 40;
    const x41 = 41;
    const x42 = 42;
    const x43 = 43;
    const x44 = 44;
    const x45 = 45;
    const x46 = 46;
    const x47 = 47;
    const x48 = 48;
    const x49 = 49;
    const x50 = 50;
    const x51 = 51;
    const x52 = 52;
}
"""
        violations = self.analyzer.analyze_solid("test.js", code, language="javascript")

        srp_violations = [v for v in violations if v.principle == "SRP" and "function" in v.description.lower()]
        assert len(srp_violations) > 0

    def test_suggest_refactoring_mapping(self):
        """Test suggest_refactoring mapping."""
        violations = [
            SolidViolation(
                principle="SRP",
                file_path="test.py",
                description="Class 'GodObject' has 20 methods",
                severity="high",
            ),
            SolidViolation(
                principle="ISP",
                file_path="test.py",
                description="Function 'complex' has 10 parameters",
                severity="medium",
            ),
            SolidViolation(
                principle="DIP",
                file_path="test.py",
                description="File has 25 concrete imports",
                severity="low",
            ),
        ]

        suggestions = self.analyzer.suggest_refactoring(violations)

        assert len(suggestions) == 3

        # Check SRP suggestion for class
        srp_class_sugg = [s for s in suggestions if "class" in s.violation.description.lower()]
        assert len(srp_class_sugg) > 0
        assert "composition" in srp_class_sugg[0].suggested_change.lower()

        # Check ISP suggestion
        isp_sugg = [s for s in suggestions if s.violation.principle == "ISP"]
        assert len(isp_sugg) > 0
        assert "dataclass" in isp_sugg[0].suggested_change.lower()

        # Check DIP suggestion
        dip_sugg = [s for s in suggestions if s.violation.principle == "DIP"]
        assert len(dip_sugg) > 0
        assert "abstract interfaces" in dip_sugg[0].suggested_change.lower()

    def test_suggest_refactoring_function_srp(self):
        """Test suggest_refactoring for function SRP violations."""
        violation = SolidViolation(
            principle="SRP",
            file_path="test.py",
            description="Function 'long_func' is 80 lines long",
            severity="medium",
        )

        suggestions = self.analyzer.suggest_refactoring([violation])

        assert len(suggestions) == 1
        assert "smaller" in suggestions[0].suggested_change.lower()
        assert "helper functions" in suggestions[0].suggested_change.lower()
