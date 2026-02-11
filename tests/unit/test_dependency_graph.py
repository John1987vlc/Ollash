"""
Unit tests for DependencyGraph system.
"""

import pytest
from unittest.mock import Mock

from src.utils.core.dependency_graph import DependencyGraph


@pytest.fixture
def logger_mock():
    """Create a mock logger."""
    return Mock()


@pytest.fixture
def dependency_graph(logger_mock):
    """Create a DependencyGraph instance."""
    return DependencyGraph(logger_mock)


@pytest.fixture
def sample_structure():
    """Create a sample project structure."""
    return {
        "folders": [
            {
                "name": "src",
                "files": ["main.py", "config.py"],
                "folders": [
                    {
                        "name": "models",
                        "files": ["user.py", "product.py"]
                    },
                    {
                        "name": "services",
                        "files": ["user_service.py", "product_service.py"]
                    }
                ]
            },
            {
                "name": "tests",
                "files": ["test_main.py", "test_user_service.py"]
            }
        ],
        "files": ["README.md", "requirements.txt"]
    }


class TestDependencyGraphBuild:
    """Test building dependency graph."""
    
    def test_build_from_structure(self, dependency_graph, sample_structure):
        """Test building graph from structure."""
        dependency_graph.build_from_structure(sample_structure)
        
        assert len(dependency_graph.file_info) > 0
        assert dependency_graph.graph is not None
    
    def test_extract_files(self, dependency_graph, sample_structure):
        """Test file extraction."""
        dependency_graph.build_from_structure(sample_structure)
        
        # Check that files were extracted
        files = list(dependency_graph.file_info.keys())
        assert any("main.py" in f for f in files)
        assert any("user.py" in f for f in files)
        assert any("test_main.py" in f for f in files)


class TestDependencyGraphFileTypes:
    """Test file type inference."""
    
    def test_infer_file_type(self, dependency_graph):
        """Test file type inference."""
        assert dependency_graph._infer_file_type("test_main.py") == "test"
        assert dependency_graph._infer_file_type("models/user.py") == "model"
        assert dependency_graph._infer_file_type("utils/helper.py") == "utility"
        assert dependency_graph._infer_file_type("config.py") == "config"
        assert dependency_graph._infer_file_type("main.py") == "other"


class TestDependencyGraphInference:
    """Test dependency inference."""
    
    def test_files_likely_related(self, dependency_graph):
        """Test relationship detection."""
        # Test case files related to source
        assert dependency_graph._files_likely_related(
            "test_user_service.py", "user_service.py"
        )
        
        # Test same directory
        assert dependency_graph._files_likely_related(
            "src/models/user.py", "src/models/product.py"
        )
        
        # Test unrelated files
        assert not dependency_graph._files_likely_related(
            "completely_different_module.py", "another_module.py"
        )


class TestGenerationOrder:
    """Test topological sorting for generation order."""
    
    def test_generation_order_exists(self, dependency_graph, sample_structure):
        """Test that generation order is computed."""
        dependency_graph.build_from_structure(sample_structure)
        
        order = dependency_graph.get_generation_order()
        assert len(order) > 0
        assert isinstance(order, list)
    
    def test_generation_order_config_first(self, dependency_graph, sample_structure):
        """Test that config files come early."""
        dependency_graph.build_from_structure(sample_structure)
        
        order = dependency_graph.get_generation_order()
        config_files = [f for f in order if "config" in f.lower()]
        
        # Config should be early (not in last quarter)
        if config_files:
            config_index = order.index(config_files[0])
            assert config_index < len(order) * 0.75


class TestContextSelection:
    """Test context retrieval for files."""
    
    def test_context_for_file(self, dependency_graph, sample_structure):
        """Test getting context for a file."""
        dependency_graph.build_from_structure(sample_structure)
        
        # Get context for a service file (should depend on models)
        dependencies = dependency_graph.get_context_for_file(
            "src/services/user_service.py", max_depth=2
        )
        
        # Should return files
        assert isinstance(dependencies, list)


class TestDependentFiles:
    """Test getting files that depend on a file."""
    
    def test_get_dependents(self, dependency_graph, sample_structure):
        """Test getting files that depend on a given file."""
        dependency_graph.build_from_structure(sample_structure)
        
        # Get dependents of a model file
        dependents = dependency_graph.get_dependents("src/models/user.py")
        
        assert isinstance(dependents, list)


class TestCircularDependencies:
    """Test circular dependency detection."""
    
    def test_circular_dependency_detection(self, logger_mock):
        """Test detection of circular dependencies."""
        graph = DependencyGraph(logger_mock)
        
        # Create structure with potential circular dependency
        graph.add_dependency("a.py", "b.py")
        graph.add_dependency("b.py", "c.py")
        graph.add_dependency("c.py", "a.py")
        
        # Detect cycles
        graph._detect_circular_dependencies()
        
        # Should have detected the cycle
        assert len(graph.circular_deps) > 0
    
    def test_break_cycles(self, logger_mock):
        """Test breaking cycles in graph."""
        graph = DependencyGraph(logger_mock)
        
        graph.add_dependency("test_main.py", "main.py")
        graph.add_dependency("main.py", "test_main.py")
        
        # Break cycle
        broken_graph = graph._break_cycles()
        
        # At least one edge should be removed
        assert len(broken_graph) <= len(graph.graph)


class TestGraphExport:
    """Test exporting graph data."""
    
    def test_to_dict(self, dependency_graph, sample_structure):
        """Test exporting graph as dictionary."""
        dependency_graph.build_from_structure(sample_structure)
        
        graph_dict = dependency_graph.to_dict()
        
        assert "files" in graph_dict
        assert "dependencies" in graph_dict
        assert "generation_order" in graph_dict
        assert len(graph_dict["files"]) > 0
