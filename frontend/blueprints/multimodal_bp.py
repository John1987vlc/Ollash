"""
Phase 5: Multimodal Input & OCR Blueprint
REST API for OCR, document ingestion, and audio transcription
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Blueprint, jsonify, request

from backend.core.kernel import AgentKernel  # Import AgentKernel
from backend.utils.core.agent_logger import AgentLogger  # For type hinting
from backend.utils.core.multimedia_ingester import MultimediaIngester
from backend.utils.core.ocr_processor import OCRProcessor, PDFOCRProcessor
from backend.utils.core.speech_transcriber import SpeechTranscriber

from werkzeug.utils import secure_filename

# Create blueprint
multimodal_bp = Blueprint("multimodal", __name__, url_prefix="/api/multimodal")

# Global managers (initialized in init_app)
ocr_processor: Optional[OCRProcessor] = None
multimedia_ingester: Optional[MultimediaIngester] = None
speech_transcriber: Optional[SpeechTranscriber] = None
logger: Optional[AgentLogger] = None  # Declare global logger with correct type
UPLOAD_FOLDER = "knowledge_workspace/ingest/uploads"


def init_app(app, ollash_root_dir: Path):
    """Initialize multimodal managers"""
    global ocr_processor, multimedia_ingester, speech_transcriber, logger

    # Ensure upload folder exists
    upload_path = ollash_root_dir / UPLOAD_FOLDER
    upload_path.mkdir(parents=True, exist_ok=True)

    # Get logger from AgentKernel, ensuring consistency

    # Get logger from AgentKernel, ensuring consistency
    _kernel = AgentKernel(ollash_root_dir=ollash_root_dir)
    logger = _kernel.get_logger()

    multimodal_workspace_path = str(
        ollash_root_dir / "knowledge_workspace"
    )  # Assumes knowledge_workspace is the subdir

    # Initialize OCR processor
    ocr_processor = OCRProcessor(workspace_path=multimodal_workspace_path)
    logger.info("OCRProcessor initialized")

    # Initialize multimedia ingester
    multimedia_ingester = MultimediaIngester(workspace_path=multimodal_workspace_path)
    multimedia_ingester.set_ocr_processor(ocr_processor)
    logger.info("MultimediaIngester initialized")

    # Initialize speech transcriber
    speech_transcriber = SpeechTranscriber(workspace_path=multimodal_workspace_path)
    logger.info("SpeechTranscriber initialized")


# ========================
# OCR Endpoints
# ========================


@multimodal_bp.route("/ocr/process", methods=["POST"])
def ocr_process_image():
    """
    Process a single image with OCR

    Request body:
    {
        "image_path": "/path/to/image.png",
        "image_id": "optional_identifier"
    }
    """
    try:
        data = request.get_json() or {}
        image_path = data.get("image_path")
        image_id = data.get("image_id")

        if not image_path:
            return jsonify({"error": "image_path required"}), 400

        result = ocr_processor.process_image(image_path, image_id)

        logger.info(
            f"OCR processed image: {image_path}",
            extra={"image_id": result.image_id, "confidence": result.confidence},
        )

        return jsonify(result.to_dict()), 200
    except FileNotFoundError as e:
        logger.warning(f"Image not found: {e}")
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        logger.warning(f"Invalid image: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"OCR processing error: {e}")
        return jsonify({"error": "OCR processing failed"}), 500


@multimodal_bp.route("/ocr/batch", methods=["POST"])
def ocr_batch_process():
    """
    Process multiple images

    Request body:
    {
        "image_paths": ["/path/to/img1.png", "/path/to/img2.png"],
        "image_ids": ["optional", "ids"]
    }
    """
    try:
        data = request.get_json() or {}
        image_paths = data.get("image_paths", [])
        image_ids = data.get("image_ids")

        if not image_paths:
            return jsonify({"error": "image_paths required"}), 400

        results = ocr_processor.process_batch(image_paths, image_ids)

        logger.info(
            f"Batch OCR processed {len(results)} images",
            extra={"avg_confidence": sum([r.confidence for r in results]) / len(results)},
        )

        return (
            jsonify(
                {
                    "results": [r.to_dict() for r in results],
                    "count": len(results),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Batch OCR error: {e}")
        return jsonify({"error": "Batch processing failed"}), 500


@multimodal_bp.route("/ocr/directory", methods=["POST"])
def ocr_directory():
    """
    Process all images in a directory

    Request body:
    {
        "directory_path": "/path/to/directory",
        "pattern": "*.png"
    }
    """
    try:
        data = request.get_json() or {}
        directory_path = data.get("directory_path")
        pattern = data.get("pattern", "*.png")

        if not directory_path:
            return jsonify({"error": "directory_path required"}), 400

        results = ocr_processor.extract_text_from_directory(directory_path, pattern)

        logger.info(
            f"OCR processed directory: {directory_path}",
            extra={"files_processed": len(results)},
        )

        return (
            jsonify(
                {
                    "results": results,
                    "count": len(results),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Directory OCR error: {e}")
        return jsonify({"error": "Directory processing failed"}), 500


@multimodal_bp.route("/ocr/pdf", methods=["POST"])
def ocr_pdf():
    """
    Process PDF file page by page

    Request body:
    {
        "pdf_path": "/path/to/document.pdf"
    }
    """
    try:
        data = request.get_json() or {}
        pdf_path = data.get("pdf_path")

        if not pdf_path:
            return jsonify({"error": "pdf_path required"}), 400

        pdf_processor = PDFOCRProcessor(ocr_processor)
        results = pdf_processor.process_pdf(pdf_path)

        logger.info(f"OCR processed PDF: {pdf_path}", extra={"pages": len(results)})

        return (
            jsonify(
                {
                    "results": {str(k): v.to_dict() for k, v in results.items()},
                    "page_count": len(results),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            200,
        )
    except FileNotFoundError as e:
        logger.warning(f"PDF not found: {e}")
        return jsonify({"error": str(e)}), 404
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        return jsonify({"error": "PDF processing requires pdf2image library"}), 400
    except Exception as e:
        logger.error(f"PDF OCR error: {e}")
        return jsonify({"error": "PDF processing failed"}), 500


@multimodal_bp.route("/ocr/stats", methods=["GET"])
def ocr_stats():
    """Get OCR processing statistics"""
    try:
        stats = ocr_processor.get_processing_stats()

        return jsonify({"stats": stats, "timestamp": datetime.now().isoformat()}), 200
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": "Failed to get stats"}), 500


# ========================
# Multimedia Ingestion Endpoints
# ========================


@multimodal_bp.route("/ingest/file", methods=["POST"])
def ingest_file():
    """
    Ingest a single document

    Request body:
    {
        "file_path": "/path/to/document.md",
        "ingest_id": "optional_identifier"
    }
    """
    try:
        data = request.get_json() or {}
        file_path = data.get("file_path")
        ingest_id = data.get("ingest_id")

        if not file_path:
            return jsonify({"error": "file_path required"}), 400

        document = multimedia_ingester.ingest_file(file_path, ingest_id)

        logger.info(
            f"Document ingested: {file_path}",
            extra={"doc_id": document.document_id, "blocks": len(document.blocks)},
        )

        return (
            jsonify({**document.to_dict(), "timestamp": datetime.now().isoformat()}),
            200,
        )
    except FileNotFoundError as e:
        logger.warning(f"File not found: {e}")
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        logger.warning(f"Invalid document: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        return jsonify({"error": "Document ingestion failed"}), 500


@multimodal_bp.route("/ingest/batch", methods=["POST"])
def ingest_batch():
    """
    Ingest multiple documents

    Request body:
    {
        "file_paths": ["/path/to/doc1.md", "/path/to/doc2.txt"],
        "ingest_ids": ["optional", "ids"]
    }
    """
    try:
        data = request.get_json() or {}
        file_paths = data.get("file_paths", [])
        ingest_ids = data.get("ingest_ids")

        if not file_paths:
            return jsonify({"error": "file_paths required"}), 400

        documents = multimedia_ingester.ingest_batch(file_paths, ingest_ids)

        logger.info(
            f"Batch ingested {len(documents)} documents",
            extra={"total_blocks": sum(len(d.blocks) for d in documents)},
        )

        return (
            jsonify(
                {
                    "results": [d.to_dict() for d in documents],
                    "count": len(documents),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Batch ingestion error: {e}")
        return jsonify({"error": "Batch ingestion failed"}), 500


@multimodal_bp.route("/ingest/directory", methods=["POST"])
def ingest_directory():
    """
    Ingest all documents in a directory

    Request body:
    {
        "directory_path": "/path/to/documents"
    }
    """
    try:
        data = request.get_json() or {}
        directory_path = data.get("directory_path")

        if not directory_path:
            return jsonify({"error": "directory_path required"}), 400

        documents = multimedia_ingester.ingest_directory(directory_path)

        logger.info(f"Directory ingested: {directory_path}", extra={"documents": len(documents)})

        return (
            jsonify(
                {
                    "results": [d.to_dict() for d in documents],
                    "count": len(documents),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Directory ingestion error: {e}")
        return jsonify({"error": "Directory ingestion failed"}), 500


@multimodal_bp.route("/ingest/normalize", methods=["POST"])
def ingest_normalize():
    """
    Normalize parsed document content

    Request body:
    {
        "document_id": "doc_id"
    }
    """
    try:
        data = request.get_json() or {}
        document_id = data.get("document_id")

        if not document_id:
            return jsonify({"error": "document_id required"}), 400

        # Retrieve document from cache
        if document_id not in multimedia_ingester.parsed_documents:
            return jsonify({"error": "Document not found"}), 404

        doc_data = multimedia_ingester.parsed_documents[document_id]
        # Reconstruct document object - need to handle dataclass conversion
        from backend.utils.core.multimedia_ingester import ContentBlock, ParsedDocument

        blocks = [ContentBlock(**b) for b in doc_data.get("blocks", [])]
        document = ParsedDocument(
            document_id=doc_data["document_id"],
            original_path=doc_data["original_path"],
            document_type=doc_data["document_type"],
            content_format=doc_data["content_format"],
            blocks=blocks,
            metadata=doc_data.get("metadata", {}),
            raw_text=doc_data.get("raw_text", ""),
        )

        normalization = multimedia_ingester.normalize_content(document)

        logger.info(
            f"Document normalized: {document_id}",
            extra={"quality": normalization.quality_score},
        )

        return (
            jsonify({**normalization.to_dict(), "timestamp": datetime.now().isoformat()}),
            200,
        )
    except Exception as e:
        logger.error(f"Normalization error: {e}")
        return jsonify({"error": "Normalization failed"}), 500


@multimodal_bp.route("/ingest/stats", methods=["GET"])
def ingest_stats():
    """Get ingestion statistics"""
    try:
        stats = multimedia_ingester.get_ingestion_stats()

        return jsonify({"stats": stats, "timestamp": datetime.now().isoformat()}), 200
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": "Failed to get stats"}), 500


# ========================
# Speech Transcription Endpoints
# ========================


@multimodal_bp.route("/upload", methods=["POST"])
def upload_file():
    """
    Upload a file for multimodal processing
    """
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400

        if file:
            filename = secure_filename(file.filename)
            ollash_root_dir = Path(request.environ.get("ollash_root_dir", "."))
            upload_path = ollash_root_dir / UPLOAD_FOLDER
            file_path = upload_path / filename
            file.save(str(file_path))

            logger.info(f"File uploaded successfully: {filename}")

            return jsonify({
                "status": "success",
                "filename": filename,
                "local_path": str(file_path),
                "relative_path": str(Path(UPLOAD_FOLDER) / filename)
            }), 200

    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({"error": f"Upload failed: {str(e)}"}), 500


@multimodal_bp.route("/speech/transcribe", methods=["POST"])
def transcribe_audio():
    """
    Transcribe audio file

    Request body:
    {
        "audio_path": "/path/to/audio.wav",
        "audio_id": "optional_identifier"
    }
    """
    try:
        data = request.get_json() or {}
        audio_path = data.get("audio_path")
        audio_id = data.get("audio_id")

        if not audio_path:
            return jsonify({"error": "audio_path required"}), 400

        result = speech_transcriber.transcribe_audio(audio_path, audio_id)

        logger.info(
            f"Audio transcribed: {audio_path}",
            extra={
                "transcript_length": len(result.transcript),
                "confidence": result.confidence,
            },
        )

        return (
            jsonify({**result.to_dict(), "timestamp": datetime.now().isoformat()}),
            200,
        )
    except FileNotFoundError as e:
        logger.warning(f"Audio file not found: {e}")
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        logger.warning(f"Invalid audio: {e}")
        return jsonify({"error": str(e)}), 400
    except ConnectionError as e:
        logger.error(f"Ollama connection error: {e}")
        return jsonify({"error": "Ollama service not available"}), 503
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return jsonify({"error": "Transcription failed"}), 500


@multimodal_bp.route("/speech/stream", methods=["POST"])
def stream_transcribe():
    """
    Stream transcription for long audio

    Request body:
    {
        "audio_path": "/path/to/audio.wav",
        "chunk_duration_ms": 1000
    }
    """
    try:
        data = request.get_json() or {}
        audio_path = data.get("audio_path")
        chunk_duration = data.get("chunk_duration_ms", 1000)

        if not audio_path:
            return jsonify({"error": "audio_path required"}), 400

        results = speech_transcriber.stream_transcription(audio_path, chunk_duration)

        logger.info(f"Audio streaming transcribed: {audio_path}", extra={"chunks": len(results)})

        return (
            jsonify(
                {
                    "results": [r.to_dict() for r in results],
                    "chunk_count": len(results),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            200,
        )
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        return jsonify({"error": "Streaming requires pydub library"}), 400
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        return jsonify({"error": "Streaming transcription failed"}), 500


@multimodal_bp.route("/speech/integrate-web", methods=["POST"])
def integrate_web_speech():
    """
    Integrate Web Speech API result

    Request body:
    {
        "audio_id": "identifier",
        "transcript": "the transcript text",
        "confidence": 0.95
    }
    """
    try:
        data = request.get_json() or {}
        audio_id = data.get("audio_id")
        transcript = data.get("transcript")
        confidence = data.get("confidence", 0.9)

        if not audio_id or not transcript:
            return jsonify({"error": "audio_id and transcript required"}), 400

        result = speech_transcriber.integrate_web_speech_result(audio_id, transcript, confidence)

        logger.info(
            f"Web Speech API result integrated: {audio_id}",
            extra={"confidence": confidence},
        )

        return (
            jsonify({**result.to_dict(), "timestamp": datetime.now().isoformat()}),
            200,
        )
    except Exception as e:
        logger.error(f"Integration error: {e}")
        return jsonify({"error": "Integration failed"}), 500


@multimodal_bp.route("/speech/analyze-confidence", methods=["POST"])
def analyze_confidence():
    """
    Analyze confidence thresholds for transcription

    Request body:
    {
        "audio_id": "identifier",
        "threshold": 0.7
    }
    """
    try:
        data = request.get_json() or {}
        audio_id = data.get("audio_id")
        threshold = data.get("threshold", 0.7)

        if not audio_id:
            return jsonify({"error": "audio_id required"}), 400

        # Find transcription
        if audio_id not in speech_transcriber.transcriptions:
            return jsonify({"error": "Transcription not found"}), 404

        trans_data = speech_transcriber.transcriptions[audio_id]
        from backend.utils.core.speech_transcriber import ConfidenceSegment, TranscriptionResult

        segments = [ConfidenceSegment(**s) for s in trans_data.get("segments", [])]
        result = TranscriptionResult(
            audio_id=audio_id,
            transcript=trans_data["transcript"],
            confidence=trans_data["confidence"],
            segments=segments,
        )

        analysis = speech_transcriber.match_confidence_thresholds(result, threshold)

        return jsonify({**analysis, "timestamp": datetime.now().isoformat()}), 200
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return jsonify({"error": "Analysis failed"}), 500


@multimodal_bp.route("/speech/summary", methods=["POST"])
def speech_summary():
    """
    Get summary of transcription

    Request body:
    {
        "audio_id": "identifier"
    }
    """
    try:
        data = request.get_json() or {}
        audio_id = data.get("audio_id")

        if not audio_id:
            return jsonify({"error": "audio_id required"}), 400

        # Find transcription
        if audio_id not in speech_transcriber.transcriptions:
            return jsonify({"error": "Transcription not found"}), 404

        trans_data = speech_transcriber.transcriptions[audio_id]
        from backend.utils.core.speech_transcriber import ConfidenceSegment, TranscriptionResult

        segments = [ConfidenceSegment(**s) for s in trans_data.get("segments", [])]
        result = TranscriptionResult(
            audio_id=audio_id,
            transcript=trans_data["transcript"],
            confidence=trans_data["confidence"],
            duration_seconds=trans_data.get("duration_seconds", 0),
            processing_time_ms=trans_data.get("processing_time_ms", 0),
            segments=segments,
        )

        summary = speech_transcriber.get_transcript_summary(result)

        return jsonify({**summary, "timestamp": datetime.now().isoformat()}), 200
    except Exception as e:
        logger.error(f"Summary error: {e}")
        return jsonify({"error": "Failed to generate summary"}), 500


@multimodal_bp.route("/speech/stats", methods=["GET"])
def speech_stats():
    """Get speech transcription statistics"""
    try:
        stats = speech_transcriber.get_transcription_stats()

        return jsonify({"stats": stats, "timestamp": datetime.now().isoformat()}), 200
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": "Failed to get stats"}), 500


# ========================
# Configuration Endpoints
# ========================


@multimodal_bp.route("/config/ocr", methods=["GET", "POST"])
def config_ocr():
    """Get or set OCR configuration"""
    try:
        if request.method == "GET":
            config = ocr_processor.config.to_dict()
            return jsonify(config), 200

        else:  # POST
            data = request.get_json() or {}
            # Update config
            for key, value in data.items():
                if hasattr(ocr_processor.config, key):
                    setattr(ocr_processor.config, key, value)

            logger.info("OCR configuration updated", extra=data)
            return jsonify(ocr_processor.config.to_dict()), 200
    except Exception as e:
        logger.error(f"Config error: {e}")
        return jsonify({"error": "Configuration failed"}), 500


@multimodal_bp.route("/config/speech", methods=["GET", "POST"])
def config_speech():
    """Get or set speech transcription configuration"""
    try:
        if request.method == "GET":
            config = speech_transcriber.config.to_dict()
            return jsonify(config), 200

        else:  # POST
            data = request.get_json() or {}
            for key, value in data.items():
                if hasattr(speech_transcriber.config, key):
                    setattr(speech_transcriber.config, key, value)

            logger.info("Speech configuration updated", extra=data)
            return jsonify(speech_transcriber.config.to_dict()), 200
    except Exception as e:
        logger.error(f"Config error: {e}")
        return jsonify({"error": "Configuration failed"}), 500


@multimodal_bp.route("/health", methods=["GET"])
def health_check():
    """Health check for multimodal services"""
    try:
        health_status = {
            "ocr_processor": "operational" if ocr_processor else "not_initialized",
            "multimedia_ingester": "operational" if multimedia_ingester else "not_initialized",
            "speech_transcriber": "operational" if speech_transcriber else "not_initialized",
            "timestamp": datetime.now().isoformat(),
        }

        return jsonify(health_status), 200
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({"error": "Health check failed"}), 500
