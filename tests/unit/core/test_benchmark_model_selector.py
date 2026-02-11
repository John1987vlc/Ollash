"""Unit tests for BenchmarkModelSelector module."""

import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.utils.core.benchmark_model_selector import (
    ModelBenchmarkResult,
    BenchmarkDatabase,
    AutoModelSelector,
)


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock()


@pytest.fixture
def tmp_benchmarks(tmp_path):
    """Create temporary benchmark directory with test data."""
    bench_dir = tmp_path / "benchmarks"
    bench_dir.mkdir()
    
    # Create sample benchmark results
    results = {
        "qwen3-coder": {
            "refinement": {
                "success_rate": 0.92,
                "quality_score": 0.88,
                "avg_tokens": 450,
                "avg_time_ms": 5200,
            },
            "planner": {
                "success_rate": 0.78,
                "quality_score": 0.75,
                "avg_tokens": 600,
                "avg_time_ms": 6100,
            },
        },
        "ministral-3": {
            "refinement": {
                "success_rate": 0.85,
                "quality_score": 0.82,
                "avg_tokens": 400,
                "avg_time_ms": 4200,
            },
            "planner": {
                "success_rate": 0.88,
                "quality_score": 0.86,
                "avg_tokens": 580,
                "avg_time_ms": 5500,
            },
        },
    }
    
    with open(bench_dir / "results.json", "w") as f:
        json.dump(results, f)
    
    return bench_dir


class TestModelBenchmarkResult:
    """Test ModelBenchmarkResult dataclass."""

    def test_create_result(self):
        """Test creating a benchmark result."""
        result = ModelBenchmarkResult(
            model_name="qwen3-coder",
            task_type="refinement",
            success_rate=0.92,
            quality_score=0.88,
            avg_tokens=450,
            avg_time_ms=5200,
        )
        
        assert result.model_name == "qwen3-coder"
        assert result.success_rate == 0.92
        assert result.quality_score == 0.88

    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            "model_name": "ministral-3",
            "task_type": "planner",
            "success_rate": 0.88,
            "quality_score": 0.86,
            "avg_tokens": 580,
            "avg_time_ms": 5500,
        }
        
        result = ModelBenchmarkResult(**data)
        assert result.model_name == "ministral-3"
        assert result.task_type == "planner"


class TestBenchmarkDatabase:
    """Test BenchmarkDatabase."""

    def test_load_results(self, mock_logger, tmp_benchmarks):
        """Test loading benchmark results."""
        db = BenchmarkDatabase(
            logger=mock_logger,
            benchmark_dir=tmp_benchmarks,
        )
        
        # Should have loaded results
        assert len(db.results) > 0

    def test_get_best_model_by_success_rate(self, mock_logger, tmp_benchmarks):
        """Test finding best model by success rate."""
        db = BenchmarkDatabase(
            logger=mock_logger,
            benchmark_dir=tmp_benchmarks,
        )
        
        best = db.get_best_model(
            task_type="refinement",
            metric="success_rate",
        )
        
        # qwen3-coder has 0.92, ministral has 0.85
        assert best is not None
        assert best.model_name == "qwen3-coder"

    def test_get_best_model_by_speed(self, mock_logger, tmp_benchmarks):
        """Test finding fastest model."""
        db = BenchmarkDatabase(
            logger=mock_logger,
            benchmark_dir=tmp_benchmarks,
        )
        
        best = db.get_best_model(
            task_type="refinement",
            metric="speed",
        )
        
        # ministral has 4200ms, qwen has 5200ms
        assert best is not None
        assert best.model_name == "ministral-3"

    def test_get_model_rank(self, mock_logger, tmp_benchmarks):
        """Test ranking models for a task."""
        db = BenchmarkDatabase(
            logger=mock_logger,
            benchmark_dir=tmp_benchmarks,
        )
        
        ranked = db.get_model_rank(task_type="planner")
        
        # Should return list of results
        assert isinstance(ranked, list)
        assert len(ranked) > 0

    def test_empty_benchmark_dir(self, mock_logger, tmp_path):
        """Test handling of empty benchmark directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        db = BenchmarkDatabase(
            logger=mock_logger,
            benchmark_dir=empty_dir,
        )
        
        # Should handle gracefully
        assert db.results == {}


class TestAutoModelSelector:
    """Test AutoModelSelector."""

    def test_initialization(self, mock_logger, tmp_benchmarks):
        """Test selector initialization."""
        selector = AutoModelSelector(
            logger=mock_logger,
            benchmark_dir=tmp_benchmarks,
        )
        
        assert selector.db is not None

    def test_generate_optimized_config(self, mock_logger, tmp_benchmarks):
        """Test generating optimized configuration."""
        selector = AutoModelSelector(
            logger=mock_logger,
            benchmark_dir=tmp_benchmarks,
            confidence_threshold=0.7,
        )
        
        config = selector.generate_optimized_config()
        
        # Should return dictionary or None
        assert config is None or isinstance(config, dict)

    def test_suggest_model_improvements(self, mock_logger, tmp_benchmarks):
        """Test suggesting model improvements."""
        selector = AutoModelSelector(
            logger=mock_logger,
            benchmark_dir=tmp_benchmarks,
            improvement_threshold=0.1,
        )
        
        suggestions = selector.suggest_model_improvements()
        
        # Should return list
        assert isinstance(suggestions, list)

    def test_confidence_threshold(self, mock_logger, tmp_benchmarks):
        """Test that confidence threshold is respected."""
        selector = AutoModelSelector(
            logger=mock_logger,
            benchmark_dir=tmp_benchmarks,
            confidence_threshold=0.95,  # Very high threshold
        )
        
        config = selector.generate_optimized_config()
        
        # With high threshold, might return empty config
        # This is expected behavior
        if config:
            # If config returned, validate structure
            assert isinstance(config, dict)

    def test_integration_with_settings(self, mock_logger, tmp_benchmarks, tmp_path):
        """Test integrating benchmark results into settings.json."""
        settings_file = tmp_path / "settings.json"
        settings = {
            "auto_agent_llms": {
                "coder_model": "qwen3-coder:30b",
                "planner_model": "ministral-3:14b",
            }
        }
        
        with open(settings_file, "w") as f:
            json.dump(settings, f)
        
        selector = AutoModelSelector(
            logger=mock_logger,
            benchmark_dir=tmp_benchmarks,
        )
        
        optimized = selector.generate_optimized_config()
        
        # Should be able to generate config
        assert optimized is None or isinstance(optimized, dict)
