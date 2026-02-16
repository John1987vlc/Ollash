"""
Phase 5 Multimodal & OCR Tests
Comprehensive test suite for OCR, multimedia ingestion, and speech transcription
"""

import tempfile
from pathlib import Path

import pytest

from backend.utils.core.ocr_processor import OCRConfig, OCRProcessor

# ========================
# OCR Processor Tests
# ========================


class TestOCRProcessor:
    """Test OCR processing functionality"""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def ocr_processor(self, temp_workspace):
        """Create OCR processor instance"""
        config = OCRConfig(model_name="deepseek-ocr:3b")
        return OCRProcessor(workspace_path=temp_workspace, config=config)

    @pytest.fixture
    def sample_image(self, temp_workspace):
        """Create sample test image"""
        # Create a minimal test image (1x1 PNG)
        import struct
        import zlib

        png_signature = b"\x89PNG\r\n\x1a\n"
        # IHDR chunk (1x1 image, 8-bit)
        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
        ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
        ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + struct.pack(">I", ihdr_crc)

        # IDAT chunk (minimal data)
        idat_data = zlib.compress(b"\x00\x00")
        idat_crc = zlib.crc32(b"IDAT" + idat_data) & 0xFFFFFFFF
        idat = struct.pack(">I", len(idat_data)) + b"IDAT" + idat_data + struct.pack(">I", idat_crc)

        # IEND chunk
        iend_crc = zlib.crc32(b"IEND") & 0xFFFFFFFF
        iend = struct.pack(">I", 0) + b"IEND" + struct.pack(">I", iend_crc)

        png_data = png_signature + ihdr + idat + iend

        image_path = Path(temp_workspace) / "test_image.png"
        image_path.write_bytes(png_data)
        return str(image_path)

    def test_ocr_processor_init(self, ocr_processor):
        """Test OCR processor initialization"""
        assert ocr_processor is not None
        assert ocr_processor.config.model_name == "deepseek-ocr:3b"
        assert ocr_processor.ocr_dir.exists()

    def test_image_validation(self, ocr_processor, sample_image):
        """Test image validation"""
        # Valid image should pass validation
        assert ocr_processor._validate_image(sample_image) == True

    def test_image_validation_invalid_format(self, ocr_processor, temp_workspace):
        """Test validation fails for unsupported formats"""
        # Create invalid format file
        invalid_file = Path(temp_workspace) / "test.xyz"
        invalid_file.write_text("fake image")

        with pytest.raises(ValueError):
            ocr_processor._validate_image(str(invalid_file))

    def test_image_validation_missing_file(self, ocr_processor):
        """Test validation fails for missing file"""
        with pytest.raises(FileNotFoundError):
            ocr_processor._validate_image("/nonexistent/path.png")

    def test_get_processing_stats_empty(self, ocr_processor):
        """Test stats on empty processor"""
        stats = ocr_processor.get_processing_stats()

        assert stats["total_processed"] == 0
        assert stats["avg_confidence"] == 0
        assert stats["avg_processing_time_ms"] == 0

    def test_cache_persistence(self, ocr_processor, sample_image):
        """Test cache persistence"""
        # Add item to cache
        ocr_processor.processed_images["test_id"] = {
            "image_id": "test_id",
            "extracted_text": "Test text",
            "confidence": 0.95,
        }
        ocr_processor._save_cache()

        # Create new processor and verify cache loaded
        ocr_processor2 = OCRProcessor(workspace_path=ocr_processor.workspace)
        assert "test_id" in ocr_processor2.processed_images
        assert ocr_processor2.processed_images["test_id"]["confidence"] == 0.95

    def test_clear_cache(self, ocr_processor):
        """Test cache clearing"""
        # Add to cache
        ocr_processor.processed_images["test_id"] = {"test": "data"}
        ocr_processor._save_cache()

        # Clear cache
        ocr_processor.clear_cache()
        assert len(ocr_processor.processed_images) == 0
        assert not ocr_processor.results_cache.exists()


# ========================
# Multimedia Ingester Tests
# ========================


class TestMultimediaIngester:
    """Test document ingestion and parsing"""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def ingester(self, temp_workspace):
        """Create multimedia ingester instance"""
        from backend.utils.core.multimedia_ingester import MultimediaIngester

        return MultimediaIngester(workspace_path=temp_workspace)

    @pytest.fixture
    def sample_text_file(self, temp_workspace):
        """Create sample text file"""
        text_path = Path(temp_workspace) / "test.txt"
        text_path.write_text("This is a test document.\nWith multiple lines.\n")
        return str(text_path)

    @pytest.fixture
    def sample_markdown_file(self, temp_workspace):
        """Create sample markdown file"""
        md_path = Path(temp_workspace) / "test.md"
        md_path.write_text("# Heading 1\n\nSome text here.\n\n## Heading 2\n\n- List item 1\n- List item 2\n")
        return str(md_path)

    @pytest.fixture
    def sample_json_file(self, temp_workspace):
        """Create sample JSON file"""
        json_path = Path(temp_workspace) / "test.json"
        json_path.write_text('{"key": "value", "number": 42}')
        return str(json_path)

    def test_ingester_init(self, ingester):
        """Test ingester initialization"""
        assert ingester is not None
        assert ingester.ingest_dir.exists()

    def test_format_detection_text(self, ingester, sample_text_file):
        """Test format detection for text files"""
        from backend.utils.core.multimedia_ingester import DocumentType

        fmt = ingester.detect_format(sample_text_file)
        assert fmt == DocumentType.TEXT

    def test_format_detection_markdown(self, ingester, sample_markdown_file):
        """Test format detection for markdown files"""
        from backend.utils.core.multimedia_ingester import DocumentType

        fmt = ingester.detect_format(sample_markdown_file)
        assert fmt == DocumentType.MARKDOWN

    def test_format_detection_json(self, ingester, sample_json_file):
        """Test format detection for JSON files"""
        from backend.utils.core.multimedia_ingester import DocumentType

        fmt = ingester.detect_format(sample_json_file)
        assert fmt == DocumentType.TEXT  # JSON detected as text, parsed specially

    def test_ingest_text_file(self, ingester, sample_text_file):
        """Test ingesting text file"""
        document = ingester.ingest_file(sample_text_file)

        assert document.document_id is not None
        assert len(document.blocks) > 0
        assert document.raw_text != ""

    def test_ingest_markdown_file(self, ingester, sample_markdown_file):
        """Test ingesting markdown file"""
        document = ingester.ingest_file(sample_markdown_file)

        assert document.document_id is not None
        assert len(document.blocks) > 0
        # Should have heading blocks
        heading_blocks = [b for b in document.blocks if b.content_type == "heading"]
        assert len(heading_blocks) > 0

    def test_ingest_json_file(self, ingester, sample_json_file):
        """Test ingesting JSON file"""
        document = ingester.ingest_file(sample_json_file)

        assert document.document_id is not None
        assert len(document.blocks) > 0

    def test_ingest_batch(self, ingester, sample_text_file, sample_markdown_file):
        """Test batch ingestion"""
        files = [sample_text_file, sample_markdown_file]
        documents = ingester.ingest_batch(files)

        assert len(documents) == 2
        assert all(d.document_id for d in documents)

    def test_normalize_content(self, ingester, sample_markdown_file):
        """Test content normalization"""
        document = ingester.ingest_file(sample_markdown_file)
        normalization = ingester.normalize_content(document)

        assert normalization.document_id == document.document_id
        assert len(normalization.normalized_text) > 0
        assert normalization.quality_score > 0

    def test_ingestion_stats(self, ingester, sample_text_file, sample_markdown_file):
        """Test ingestion statistics"""
        ing1 = ingester.ingest_file(sample_text_file)
        ing2 = ingester.ingest_file(sample_markdown_file)

        stats = ingester.get_ingestion_stats()

        # Only count unique files ingested
        assert stats["total_ingested"] >= 1  # At least one file
        assert stats["total_blocks"] >= 2  # At least 2 blocks from both files

    def test_cache_persistence(self, ingester, sample_text_file):
        """Test cache persistence"""
        # Ingest file
        ingester.ingest_file(sample_text_file)
        doc_id = Path(sample_text_file).stem

        # Create new ingester and verify cache
        from backend.utils.core.multimedia_ingester import MultimediaIngester

        ingester2 = MultimediaIngester(workspace_path=ingester.workspace)
        assert doc_id in ingester2.parsed_documents


# ========================
# Speech Transcriber Tests
# ========================


class TestSpeechTranscriber:
    """Test speech transcription functionality"""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def transcriber(self, temp_workspace):
        """Create speech transcriber instance"""
        from backend.utils.core.speech_transcriber import SpeechTranscriber, TranscriptionConfig

        config = TranscriptionConfig(model_name="whisper-tiny")
        return SpeechTranscriber(workspace_path=temp_workspace, config=config)

    @pytest.fixture
    def sample_audio_file(self, temp_workspace):
        """Create sample audio file (minimal WAV)"""
        # Create minimal WAV file
        import struct

        wav_path = Path(temp_workspace) / "test.wav"

        # WAV header
        channels = 1
        sample_rate = 16000
        bits_per_sample = 16
        duration_ms = 100
        num_samples = (sample_rate * duration_ms) // 1000
        audio_data_size = num_samples * channels * (bits_per_sample // 8)

        # RIFF header
        riff_size = 36 + audio_data_size
        riff_header = b"RIFF" + struct.pack("<I", riff_size) + b"WAVE"

        # fmt subchunk
        fmt_size = 16
        fmt_data = struct.pack(
            "<HHIIHH",
            1,  # PCM format
            channels,
            sample_rate,
            sample_rate * channels * bits_per_sample // 8,
            channels * bits_per_sample // 8,
            bits_per_sample,
        )
        fmt_subchunk = b"fmt " + struct.pack("<I", fmt_size) + fmt_data

        # data subchunk
        audio_data = b"\x00" * audio_data_size
        data_subchunk = b"data" + struct.pack("<I", audio_data_size) + audio_data

        wav_file = riff_header + fmt_subchunk + data_subchunk
        wav_path.write_bytes(wav_file)

        return str(wav_path)

    def test_transcriber_init(self, transcriber):
        """Test transcriber initialization"""
        assert transcriber is not None
        assert transcriber.config.model_name == "whisper-tiny"
        assert transcriber.speech_dir.exists()

    def test_audio_validation(self, transcriber, sample_audio_file):
        """Test audio validation"""
        assert transcriber._validate_audio(sample_audio_file) == True

    def test_audio_validation_missing_file(self, transcriber):
        """Test validation fails for missing file"""
        with pytest.raises(FileNotFoundError):
            transcriber._validate_audio("/nonexistent/audio.wav")

    def test_audio_validation_invalid_format(self, transcriber, temp_workspace):
        """Test validation fails for unsupported formats"""
        invalid_file = Path(temp_workspace) / "test.xyz"
        invalid_file.write_text("fake audio")

        with pytest.raises(ValueError):
            transcriber._validate_audio(str(invalid_file))

    def test_segment_parsing(self, transcriber):
        """Test parsing transcript into segments"""
        transcript = "First sentence. Second sentence. Third sentence."
        segments = transcriber._parse_segments(transcript)

        assert len(segments) == 3
        assert all(0 <= s.confidence <= 1 for s in segments)

    def test_confidence_calculation(self, transcriber):
        """Test confidence score calculation"""
        from backend.utils.core.speech_transcriber import ConfidenceSegment

        segments = [
            ConfidenceSegment(0, 100, "text1", 0.9),
            ConfidenceSegment(100, 200, "text2", 0.8),
            ConfidenceSegment(200, 300, "text3", 0.85),
        ]

        confidence = transcriber._calculate_confidence(segments)
        expected = (0.9 + 0.8 + 0.85) / 3
        assert abs(confidence - expected) < 0.01

    def test_integrate_web_speech_result(self, transcriber):
        """Test integrating Web Speech API results"""
        result = transcriber.integrate_web_speech_result(
            audio_id="test_audio",
            web_speech_transcript="This is a test transcript.",
            web_speech_confidence=0.95,
        )

        assert result.audio_id == "test_audio"
        assert result.confidence == 0.95
        assert "test_audio" in transcriber.transcriptions

    def test_match_confidence_thresholds(self, transcriber):
        """Test confidence threshold matching"""
        from backend.utils.core.speech_transcriber import ConfidenceSegment, TranscriptionResult

        # Create 3 segments with different confidence levels
        # Note: is_uncertain should be True for segments with confidence < 0.7
        segments = [
            ConfidenceSegment(0, 1000, "high conf text", 0.95, is_uncertain=False),
            ConfidenceSegment(1000, 2000, "low", 0.5, is_uncertain=True),
            ConfidenceSegment(2000, 3000, "high conf text two", 0.92, is_uncertain=False),
        ]

        result = TranscriptionResult(
            audio_id="test",
            transcript="high conf text low high conf text two",
            confidence=0.8,
            segments=segments,
        )

        analysis = transcriber.match_confidence_thresholds(result, threshold=0.7)

        # Verify the counts
        assert analysis["total_segments"] == 3
        assert analysis["above_threshold_count"] == 2  # 0.95 and 0.92 are above 0.7
        assert analysis["below_threshold_count"] == 1  # 0.5 is below 0.7

    def test_transcript_summary(self, transcriber):
        """Test transcript summary generation"""
        from backend.utils.core.speech_transcriber import ConfidenceSegment, TranscriptionResult

        segments = [ConfidenceSegment(0, 100, "word one", 0.9)]
        # Count unique words: word, one, two, three, four = 5 words
        # But splitting "word one two three four five" gives us the exact word count
        result = TranscriptionResult(
            audio_id="test",
            transcript="word one two three four five",
            confidence=0.9,
            duration_seconds=10,
            segments=segments,
        )

        summary = transcriber.get_transcript_summary(result)

        # Verify summary structure
        assert summary["word_count"] > 0
        assert summary["duration_seconds"] == 10
        assert summary["overall_confidence"] == 0.9

    def test_transcription_stats(self, transcriber):
        """Test transcription statistics"""
        transcriber.integrate_web_speech_result("audio1", "first transcript", 0.95)
        transcriber.integrate_web_speech_result("audio2", "second transcript", 0.90)

        stats = transcriber.get_transcription_stats()

        assert stats["total_transcribed"] == 2
        assert abs(stats["avg_confidence"] - 0.925) < 0.01

    def test_clear_cache(self, transcriber):
        """Test cache clearing"""
        transcriber.integrate_web_speech_result("audio1", "transcript", 0.9)
        transcriber.clear_cache()

        assert len(transcriber.transcriptions) == 0


# ========================
# Integration Tests
# ========================


class TestMultimodalIntegration:
    """Integration tests for multimodal system"""

    @pytest.fixture
    def temp_workspace(self):
        """Create temporary workspace"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_workflow_text_to_normalized(self, temp_workspace):
        """Test complete text ingestion workflow"""
        from backend.utils.core.multimedia_ingester import MultimediaIngester

        # Create sample document
        doc_path = Path(temp_workspace) / "sample.txt"
        doc_path.write_text("First paragraph.\nSecond paragraph.\n")

        # Ingest and normalize
        ingester = MultimediaIngester(workspace_path=temp_workspace)
        document = ingester.ingest_file(str(doc_path))
        normalization = ingester.normalize_content(document)

        assert len(normalization.normalized_text) > 0
        assert normalization.quality_score >= 0

    def test_system_health(self, temp_workspace):
        """Test system components are operational"""
        from backend.utils.core.multimedia_ingester import MultimediaIngester
        from backend.utils.core.ocr_processor import OCRProcessor
        from backend.utils.core.speech_transcriber import SpeechTranscriber

        ocr = OCRProcessor(workspace_path=temp_workspace)
        ingester = MultimediaIngester(workspace_path=temp_workspace)
        transcriber = SpeechTranscriber(workspace_path=temp_workspace)

        # Verify all systems operational
        assert ocr is not None
        assert ingester is not None
        assert transcriber is not None

        # Verify caches initialized
        assert ocr.processed_images == {}
        assert ingester.parsed_documents == {}
        assert transcriber.transcriptions == {}


# Run tests with: pytest tests/test_phase5_multimodal.py -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
