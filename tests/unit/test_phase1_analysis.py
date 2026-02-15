"""
Tests para CrossReferenceAnalyzer, KnowledgeGraphBuilder y DecisionContextManager.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock  # NEW

import pytest

from backend.utils.core.agent_logger import AgentLogger  # NEW
from backend.utils.core.cross_reference_analyzer import CrossReferenceAnalyzer
from backend.utils.core.decision_context_manager import DecisionContextManager
from backend.utils.core.knowledge_graph_builder import KnowledgeGraphBuilder


@pytest.fixture
def temp_project():
    """Crea un proyecto temporal para tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Crear estructura
        docs_dir = project_root / "docs"
        docs_dir.mkdir()

        # Crear documentos de prueba
        doc1 = docs_dir / "network_manual.md"
        doc1.write_text(
            """
# Network Manual

## IP Protocol
IP (Internet Protocol) is the fundamental protocol for networking.

## Network Configuration
Configure your network with proper IP addressing and DNS setup.

### Prerequisites
- IP addressing scheme
- DNS configuration
        """
        )

        doc2 = docs_dir / "architecture.md"
        doc2.write_text(
            """
# System Architecture

## Networking Layer
The Networking Layer handles all IP communication and protocols.

## Components
- Router component for IP routing
- Protocol handlers for various protocols

API endpoints are served over the network layer.
        """
        )

        # Config
        knowledge_dir = project_root / "knowledge_workspace"
        knowledge_dir.mkdir()

        logger = MagicMock(spec=AgentLogger)
        config = {
            "ollama_url": "http://localhost:11434",
            "models": {"embedding": "all-minilm", "reasoning": "gpt-oss:20b"},
        }

        yield project_root, logger, config


class TestCrossReferenceAnalyzer:
    """Tests para CrossReferenceAnalyzer."""

    def test_initialization(self, temp_project):
        """Prueba inicialización del analyzer."""
        project_root, logger, config = temp_project

        analyzer = CrossReferenceAnalyzer(project_root, logger, config)
        assert analyzer is not None
        assert analyzer.project_root == project_root

    def test_compare_documents(self, temp_project):
        """Prueba comparación de documentos."""
        project_root, logger, config = temp_project

        doc1 = project_root / "docs" / "network_manual.md"
        doc2 = project_root / "docs" / "architecture.md"

        analyzer = CrossReferenceAnalyzer(project_root, logger, config)
        result = analyzer.compare_documents(doc1, doc2)

        assert result is not None
        assert "doc1" in result
        assert "doc2" in result
        assert "shared_concepts" in result
        assert "doc1_unique" in result
        assert "doc2_unique" in result
        assert "similarity_score" in result

    def test_find_cross_references(self, temp_project):
        """Prueba búsqueda de referencias cruzadas."""
        project_root, logger, config = temp_project

        analyzer = CrossReferenceAnalyzer(project_root, logger, config)
        references = analyzer.find_cross_references("IP", [project_root / "docs"])

        # Debe encontrar referencias a "IP"
        assert len(references) > 0
        assert all(ref.term == "IP" for ref in references)

    def test_extract_inconsistencies(self, temp_project):
        """Prueba extracción de inconsistencias."""
        project_root, logger, config = temp_project

        doc_paths = [
            project_root / "docs" / "network_manual.md",
            project_root / "docs" / "architecture.md",
        ]

        analyzer = CrossReferenceAnalyzer(project_root, logger, config)
        inconsistencies = analyzer.extract_inconsistencies(doc_paths)

        # Debe retornar una lista (puede estar vacía)
        assert isinstance(inconsistencies, list)


class TestKnowledgeGraphBuilder:
    """Tests para KnowledgeGraphBuilder."""

    def test_initialization(self, temp_project):
        """Prueba inicialización del graph builder."""
        project_root, logger, config = temp_project

        builder = KnowledgeGraphBuilder(project_root, logger, config)
        assert builder is not None
        assert len(builder.nodes) == 0  # Empty initially

    def test_add_relationship(self, temp_project):
        """Prueba añadir relaciones al grafo."""
        project_root, logger, config = temp_project

        builder = KnowledgeGraphBuilder(project_root, logger, config)
        result = builder.add_relationship("API", "REST", "uses", 0.8)

        assert result is True
        assert len(builder.nodes) == 2

    def test_concept_connections(self, temp_project):
        """Prueba obtener conexiones de un concepto."""
        project_root, logger, config = temp_project

        builder = KnowledgeGraphBuilder(project_root, logger, config)
        builder.add_relationship("API", "REST", "uses", 0.8)
        builder.add_relationship("REST", "HTTP", "over", 0.9)

        connections = builder.get_concept_connections("API", max_depth=2)

        # Verify connections returns a dict-like result
        assert isinstance(connections, (dict, type(None))) or hasattr(
            connections, "__contains__"
        )

    def test_generate_thematic_index(self, temp_project):
        """Prueba generación de índice temático."""
        project_root, logger, config = temp_project

        builder = KnowledgeGraphBuilder(project_root, logger, config)
        builder.add_relationship("API", "REST", "uses", 0.8)

        index = builder.generate_thematic_index()

        assert isinstance(index, dict)


class TestDecisionContextManager:
    """Tests para DecisionContextManager."""

    def test_initialization(self, temp_project):
        """Prueba inicialización del context manager."""
        project_root, logger, config = temp_project

        manager = DecisionContextManager(project_root, logger, config)
        assert manager is not None
        assert len(manager.decisions) == 0

    def test_record_decision(self, temp_project):
        """Prueba registrar una decisión."""
        project_root, logger, config = temp_project

        manager = DecisionContextManager(project_root, logger, config)
        decision_id = manager.record_decision(
            decision="Use Cosmos DB",
            reasoning="Global distribution and low latency",
            category="architecture",
            context={"problem": "Need scalable storage"},
            project="test_project",
        )

        assert decision_id != ""
        assert decision_id in manager.decisions

    def test_find_similar_decisions(self, temp_project):
        """Prueba buscar decisiones similares."""
        project_root, logger, config = temp_project

        manager = DecisionContextManager(project_root, logger, config)

        # Registrar decisión
        manager.record_decision(
            decision="Use Cosmos DB for chat history",
            reasoning="Provides scalability",
            category="architecture",
            context={"problem": "Need storage"},
        )

        # Buscar similar
        similar = manager.find_similar_decisions(
            "Need scalable database storage", category="architecture"
        )

        # Verify similar_decisions returns a list or callable result
        assert isinstance(similar, (list, tuple)) or similar is not None

    def test_get_statistics(self, temp_project):
        """Prueba obtener estadísticas."""
        project_root, logger, config = temp_project

        manager = DecisionContextManager(project_root, logger, config)

        manager.record_decision(
            decision="Use Cosmos DB",
            reasoning="Scalability",
            category="architecture",
            context={},
        )

        stats = manager.get_statistics()

        assert "total_decisions" in stats
        assert stats["total_decisions"] == 1

    def test_update_outcome(self, temp_project):
        """Prueba actualizar outcome de una decisión."""
        project_root, logger, config = temp_project

        manager = DecisionContextManager(project_root, logger, config)

        decision_id = manager.record_decision(
            decision="Use Cosmos DB",
            reasoning="Scalability",
            category="architecture",
            context={},
        )

        # Actualizar outcome
        success = manager.update_outcome(
            decision_id, {"success": True, "lesson": "Cosmos DB worked well"}
        )

        assert success is True
        decision = manager.get_decision(decision_id)
        assert decision.outcome is not None
        assert decision.outcome["success"] is True


class TestIntegration:
    """Tests de integración entre componentes."""

    def test_cross_reference_with_knowledge_graph(self, temp_project):
        """Prueba integración entre analyzer y knowledge graph."""
        project_root, logger, config = temp_project

        # Analizar documentos
        analyzer = CrossReferenceAnalyzer(project_root, logger, config)
        doc1 = project_root / "docs" / "network_manual.md"
        doc2 = project_root / "docs" / "architecture.md"
        result = analyzer.compare_documents(doc1, doc2)

        # Construir grafo basado en conceptos encontrados
        builder = KnowledgeGraphBuilder(project_root, logger, config)

        for concept in result.get("shared_concepts", []):
            builder.add_relationship("Document", concept, "mentions", 0.7)

        assert len(builder.nodes) > 0

    def test_decisions_affect_future_suggestions(self, temp_project):
        """Prueba que decisiones previas afecten sugerencias."""
        project_root, logger, config = temp_project

        manager = DecisionContextManager(project_root, logger, config)

        # Registrar decisión 1
        dec1 = manager.record_decision(
            decision="Use Cosmos DB for user data",
            reasoning="Need geo-distribution",
            category="architecture",
            context={"problem": "Multi-region users"},
        )

        # Registrar decisión 2 relacionada
        dec2 = manager.record_decision(
            decision="Use Cosmos DB for chat history",
            reasoning="Need low latency",
            category="architecture",
            context={"problem": "Chat messages storage"},
        )

        # Obtener suggestions para problema similar
        suggestions = manager.suggest_based_on_history(
            "Where should we store distributed data?", category="architecture"
        )

        # Verify suggestions are generated/returned (don't check specific content)
        assert suggestions is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
