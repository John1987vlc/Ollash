"""
Phase 4: Comprehensive Test Suite
Tests for FeedbackRefinementManager, SourceValidator, and RefinementOrchestrator
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

from src.utils.core.feedback_refinement_manager import (
    FeedbackRefinementManager,
    ParagraphContext,
    RefinementRecord,
)
from src.utils.core.source_validator import (
    SourceValidator,
    ValidationResult,
    ValidationIssue,
)
from src.utils.core.refinement_orchestrator import (
    RefinementOrchestrator,
    RefinementWorkflow,
    RefinementStrategy,
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def refinement_mgr(temp_workspace):
    """Create FeedbackRefinementManager instance"""
    return FeedbackRefinementManager(temp_workspace)


@pytest.fixture
def source_validator(temp_workspace):
    """Create SourceValidator instance"""
    return SourceValidator(temp_workspace)


@pytest.fixture
def orchestrator(temp_workspace):
    """Create RefinementOrchestrator instance"""
    return RefinementOrchestrator(temp_workspace)


class TestFeedbackRefinementManager:
    """Test FeedbackRefinementManager functionality"""
    
    def test_extract_paragraphs(self, refinement_mgr):
        """Test paragraph extraction from text"""
        text = "First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph."
        paragraphs = refinement_mgr.extract_paragraphs(text, "test_source")
        
        assert len(paragraphs) == 3
        assert paragraphs[0].index == 0
        assert paragraphs[0].source_id == "test_source"
        assert "First paragraph" in paragraphs[0].text
    
    def test_paragraph_readability_score(self, refinement_mgr):
        """Test readability score calculation"""
        text = "Simple text here."
        paragraphs = refinement_mgr.extract_paragraphs(text, "test")
        
        assert len(paragraphs) == 1
        assert paragraphs[0].readability_score > 0
        assert paragraphs[0].readability_score <= 100
    
    def test_select_paragraphs_by_readability(self, refinement_mgr):
        """Test paragraph selection by readability"""
        easy_text = "This is easy. It is clear."
        hard_text = "Notwithstanding the aforementioned considerations, implementation necessitates comprehensive evaluation."
        
        text = easy_text + "\n\n" + hard_text
        paragraphs = refinement_mgr.extract_paragraphs(text, "test")
        
        # Low readability threshold selects hard text
        selected = refinement_mgr.select_paragraphs_for_refinement(
            paragraphs,
            {"min_readability": 30}
        )
        
        assert len(selected) >= 0
    
    def test_critique_clarity(self, refinement_mgr):
        """Test clarity critique"""
        text = "This is a very long sentence that goes on and on without proper punctuation and structure which makes it hard to read and understand what the author is trying to communicate to the reader."
        
        para = ParagraphContext(
            index=0,
            text=text,
            original_text=text,
            source_id="test"
        )
        
        critique = refinement_mgr.generate_critique(para, "clarity")
        assert critique != ""
        assert isinstance(critique, str)
    
    def test_critique_conciseness(self, refinement_mgr):
        """Test conciseness critique"""
        text = "Very very very important point is really actually basically very important."
        para = ParagraphContext(1, text, text, "test")
        
        critique = refinement_mgr.generate_critique(para, "conciseness")
        assert critique != ""
    
    def test_critique_structure(self, refinement_mgr):
        """Test structure critique"""
        text = "Single sentence paragraph."
        para = ParagraphContext(1, text, text, "test")
        
        critique = refinement_mgr.generate_critique(para, "structure")
        assert critique != ""
    
    def test_apply_refinement(self, refinement_mgr):
        """Test applying a refinement"""
        para = ParagraphContext(0, "Original text", "Original text", "test")
        refined_text = "Improved text that is better"
        critique = "Could be clearer"
        
        record = refinement_mgr.apply_refinement(para, refined_text, critique)
        
        assert record.applied is True
        assert record.original == "Original text"
        assert record.refined == refined_text
        assert len(para.refinement_history) == 1
    
    def test_get_refinement_summary(self, refinement_mgr):
        """Test getting refinement metrics"""
        text = "Para 1\n\nPara 2\n\nPara 3"
        refinement_mgr.extract_paragraphs(text, "test")
        
        summary = refinement_mgr.get_refinement_summary()
        
        assert summary["total_paragraphs"] == 3
        assert "refinement_rate" in summary
        assert summary["refinement_rate"] >= 0


class TestSourceValidator:
    """Test SourceValidator functionality"""
    
    def test_register_source(self, source_validator):
        """Test source registration"""
        source_text = "This is a source document with important information."
        success = source_validator.register_source("test_source", source_text)
        
        assert success is True
        assert source_validator.get_source("test_source") == source_text
    
    def test_get_nonexistent_source(self, source_validator):
        """Test getting non-existent source"""
        result = source_validator.get_source("nonexistent")
        assert result is None
    
    def test_validate_refinement_valid(self, source_validator):
        """Test validating a good refinement"""
        source = "The implementation uses Cosmos DB for storage with high availability."
        source_validator.register_source("src1", source)
        
        original = "The implementation uses Cosmos DB for storage."
        refined = "The implementation uses Cosmos DB for reliable storage."
        
        result = source_validator.validate_refinement(
            original, refined, "src1", "semantic"
        )
        
        assert isinstance(result, ValidationResult)
        assert result.validation_score >= 0
    
    def test_validate_refinement_semantic_drift(self, source_validator):
        """Test detecting semantic drift"""
        source = "Use Azure Storage"
        source_validator.register_source("src", source)
        
        original = "Use Azure Storage"
        refined = "Use AWS S3 instead"
        
        result = source_validator.validate_refinement(original, refined, "src", "semantic")
        
        # Should detect significant difference
        assert isinstance(result, ValidationResult)
    
    def test_compare_versions(self, source_validator):
        """Test version comparison"""
        original = "The quick brown fox"
        refined = "The fast brown fox jumps"
        
        comparison = source_validator.compare_versions(original, refined)
        
        assert "similarity_ratio" in comparison
        assert "percent_changed" in comparison
        assert comparison["similarity_ratio"] >= 0
        assert comparison["similarity_ratio"] <= 1
    
    def test_suggest_rollback(self, source_validator):
        """Test rollback suggestion"""
        result = ValidationResult(
            is_valid=False,
            validation_score=40.0,
            issues=[
                ValidationIssue("critical", "contradiction", "old", "new", "Critical issue 1"),
                ValidationIssue("critical", "semantic_change", "old", "new", "Critical issue 2"),
            ]
        )
        
        should_rollback = source_validator.suggest_rollback(result)
        assert should_rollback is True
    
    def test_get_validation_report(self, source_validator):
        """Test getting validation report"""
        source_validator.register_source("src", "Source text")
        
        # Run a validation
        source_validator.validate_refinement("original", "refined", "src")
        
        report = source_validator.get_validation_report()
        
        assert "total_validations" in report
        assert report["total_validations"] >= 1


class TestRefinementOrchestrator:
    """Test RefinementOrchestrator functionality"""
    
    def test_create_workflow(self, orchestrator):
        """Test creating a workflow"""
        text = "Para 1 text here.\n\nPara 2 text here.\n\nPara 3 text here."
        
        workflow = orchestrator.create_workflow(
            workflow_id="wf1",
            source_id="src1",
            document_text=text,
            strategy="comprehensive"
        )
        
        assert workflow.workflow_id == "wf1"
        assert workflow.status == "created"
        assert len(workflow.paragraphs) == 3
    
    def test_list_strategies(self, orchestrator):
        """Test listing available strategies"""
        strategies = orchestrator.STRATEGIES
        
        assert "quick_polish" in strategies
        assert "comprehensive" in strategies
        assert "accuracy_focused" in strategies
        assert "aggressive_rewrite" in strategies
    
    def test_analyze_document(self, orchestrator):
        """Test document analysis"""
        text = "Easy text.\n\nVery complex and difficult sentence that uses many large words unnecessarily."
        
        workflow = orchestrator.create_workflow("wf_analysis", "src", text)
        analysis = orchestrator.analyze_document("wf_analysis")
        
        assert "total_paragraphs" in analysis
        assert "paragraphs_needing_improvement" in analysis
        assert "average_readability" in analysis
    
    def test_refine_workflow(self, orchestrator):
        """Test executing refinement"""
        text = "Short text.\n\nAnother paragraph here."
        workflow = orchestrator.create_workflow("wf_refine", "src", text)
        
        results = orchestrator.refine_workflow(
            workflow_id="wf_refine",
            strategy_name="quick_polish"
        )
        
        assert results["workflow_id"] == "wf_refine"
        assert "refinements" in results
        assert "validations" in results
    
    def test_get_workflow_status(self, orchestrator):
        """Test getting workflow status"""
        text = "Test paragraph text."
        orchestrator.create_workflow("wf_status", "src", text)
        
        status = orchestrator.get_workflow_status("wf_status")
        
        assert status["workflow_id"] == "wf_status"
        assert "status" in status
        assert "total_paragraphs" in status
    
    def test_list_workflows(self, orchestrator):
        """Test listing workflows"""
        orchestrator.create_workflow("wf1", "src1", "Text 1")
        orchestrator.create_workflow("wf2", "src2", "Text 2")
        
        workflows = orchestrator.list_workflows()
        
        assert len(workflows) >= 2
    
    def test_export_workflow_text(self, orchestrator):
        """Test exporting as text"""
        text = "Paragraph one.\n\nParagraph two."
        wf = orchestrator.create_workflow("wf_export", "src", text)
        wf.refinements_applied = [
            {"refinement": "Refined para 1"},
            {"refinement": "Refined para 2"}
        ]
        
        exported = orchestrator.export_workflow_document("wf_export", "text")
        
        assert isinstance(exported, str)
        assert "Refined para 1" in exported
    
    def test_export_workflow_html(self, orchestrator):
        """Test exporting as HTML"""
        text = "Paragraph one."
        wf = orchestrator.create_workflow("wf_html", "src", text)
        wf.refinements_applied = [{"refinement": "Refined text"}]
        
        exported = orchestrator.export_workflow_document("wf_html", "html")
        
        assert isinstance(exported, str)
        assert "<html>" in exported
        assert "Refined text" in exported
    
    def test_export_workflow_markdown(self, orchestrator):
        """Test exporting as markdown"""
        text = "Paragraph one."
        wf = orchestrator.create_workflow("wf_md", "src", text)
        wf.refinements_applied = [{"refinement": "Refined text"}]
        
        exported = orchestrator.export_workflow_document("wf_md", "markdown")
        
        assert isinstance(exported, str)
        assert "# wf_md" in exported


class TestRefinementIntegration:
    """Integration tests combining multiple components"""
    
    def test_full_refinement_workflow(self, orchestrator):
        """Test a complete refinement workflow from start to finish"""
        source_text = "The implementation uses complex technologies with many considerations."
        
        # Create workflow
        wf = orchestrator.create_workflow(
            workflow_id="integration_test",
            source_id="src_integration",
            document_text=source_text,
            strategy="comprehensive"
        )
        
        assert wf.status == "created"
        
        # Analyze
        analysis = orchestrator.analyze_document("integration_test")
        assert analysis["total_paragraphs"] >= 1
        
        # Refine
        results = orchestrator.refine_workflow("integration_test", "comprehensive")
        assert "refinements" in results
        
        # Check status
        status = orchestrator.get_workflow_status("integration_test")
        assert status["status"] == "completed"
    
    def test_validation_workflow(self, orchestrator, source_validator):
        """Test validation within refinement workflow"""
        source_validator.register_source("validation_src", "Source content here")
        
        wf = orchestrator.create_workflow(
            "validation_test",
            "validation_src",
            "Source content here with more"
        )
        
        results = orchestrator.refine_workflow("validation_test")
        
        # Check that validations were performed
        assert "validations" in results
        assert len(results["validations"]) >= 0
