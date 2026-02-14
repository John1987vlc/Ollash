"""
Unit Tests for MultiFormatIngester
Tests PDF, DOCX, PPTX, TXT, and Markdown extraction
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from backend.utils.core.multi_format_ingester import MultiFormatIngester
from backend.utils.core.agent_logger import AgentLogger


@pytest.fixture
def logger():
    """Mock logger for testing"""
    logger = Mock(spec=AgentLogger)
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
def ingester(logger):
    """Initialize MultiFormatIngester with mock logger"""
    return MultiFormatIngester(logger, config={})


class TestMultiFormatIngester:
    """Test suite for MultiFormatIngester"""

    def test_supported_formats(self, ingester):
        """Test that all expected formats are supported"""
        expected_formats = {".pdf", ".docx", ".pptx", ".txt", ".md", ".markdown"}
        assert ingester.SUPPORTED_FORMATS == expected_formats

    def test_extract_text_file(self, ingester, logger):
        """Test extracting text from plain TXT file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("Test content\nLine 2")
            f.flush()
            file_path = Path(f.name)
        
        try:
            result = ingester.ingest_file(file_path)
            assert result is not None
            assert "Test content" in result
            assert "Line 2" in result
        finally:
            file_path.unlink()

    def test_extract_markdown_file(self, ingester):
        """Test extracting Markdown file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# Title\n## Subtitle\nContent here")
            f.flush()
            file_path = Path(f.name)
        
        try:
            result = ingester.ingest_file(file_path)
            assert result is not None
            assert "Title" in result
            assert "Content here" in result
        finally:
            file_path.unlink()

    def test_unsupported_format(self, ingester, logger):
        """Test that unsupported formats return None"""
        with tempfile.NamedTemporaryFile(suffix='.xyz', delete=False) as f:
            file_path = Path(f.name)
        
        try:
            result = ingester.ingest_file(file_path)
            assert result is None
            logger.warning.assert_called()
        finally:
            file_path.unlink()

    def test_nonexistent_file(self, ingester):
        """Test handling of nonexistent files"""
        result = ingester.ingest_file(Path("/nonexistent/file.txt"))
        assert result is None

    def test_get_file_metadata_success(self, ingester):
        """Test file metadata extraction"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("One Two Three Four Five")
            f.flush()
            file_path = Path(f.name)
        
        try:
            metadata = ingester.get_file_metadata(file_path)
            assert metadata["extraction_success"] is True
            assert metadata["word_count"] == 5
            assert metadata["format"] == ".txt"
            assert "file" in metadata
            assert "size_bytes" in metadata
        finally:
            file_path.unlink()

    def test_ingest_directory(self, ingester):
        """Test ingesting all files in a directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create multiple test files
            (tmpdir_path / "file1.txt").write_text("Content 1")
            (tmpdir_path / "file2.md").write_text("# Content 2")
            (tmpdir_path / "file3.xyz").write_text("Unsupported")
            
            results = ingester.ingest_directory(tmpdir_path)
            
            assert len(results) >= 2  # At least txt and md
            assert "file1.txt" in results
            assert "file2.md" in results
            assert "Content 1" in results["file1.txt"]

    def test_encoding_fallback(self, ingester):
        """Test fallback encoding when UTF-8 fails"""
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.txt', delete=False) as f:
            # Write latin-1 encoded content
            f.write("Café".encode('latin-1'))
            f.flush()
            file_path = Path(f.name)
        
        try:
            result = ingester.ingest_file(file_path)
            # Should succeed with fallback encoding
            assert result is not None
        finally:
            file_path.unlink()

    @patch('backend.utils.core.multi_format_ingester.MultiFormatIngester._extract_pdf')
    def test_pdf_extraction_called(self, mock_pdf, ingester):
        """Test that PDF extraction is called for PDF files"""
        mock_pdf.return_value = "PDF Content"
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            file_path = Path(f.name)
        
        try:
            result = ingester.ingest_file(file_path)
            mock_pdf.assert_called_once_with(file_path)
        finally:
            file_path.unlink()

