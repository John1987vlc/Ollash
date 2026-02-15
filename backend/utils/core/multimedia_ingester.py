"""
Phase 5: Multimedia Ingester
Handles parsing and normalization of various document formats
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path
from enum import Enum


class DocumentType(Enum):
    """Supported document types"""
    TEXT = "text"
    MARKDOWN = "markdown"
    PDF = "pdf"
    IMAGE = "image"
    DOCX = "docx"
    UNKNOWN = "unknown"


class ContentFormat(Enum):
    """Normalized content formats"""
    PLAIN_TEXT = "plain_text"
    STRUCTURED = "structured"
    MARKDOWN = "markdown"
    JSON = "json"


@dataclass
class ContentBlock:
    """Single block of parsed content"""
    block_id: str
    content: str
    content_type: str  # "text", "heading", "list", "table", etc.
    level: int = 0  # For hierarchical content (heading levels, list nesting)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self):
        return asdict(self)


@dataclass
class ParsedDocument:
    """Parsed document with normalized content"""
    document_id: str
    original_path: str
    document_type: DocumentType
    content_format: ContentFormat
    blocks: List[ContentBlock]
    metadata: Dict = field(default_factory=dict)
    raw_text: str = ""
    processing_time_ms: float = 0.0
    parsed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        return asdict(self)
    
    def get_plain_text(self) -> str:
        """Extract plain text from all blocks"""
        return "\n".join([block.content for block in self.blocks])


@dataclass
class ContentNormalization:
    """Result of content normalization"""
    document_id: str
    normalized_text: str
    structure: List[Dict]  # Hierarchical structure
    metadata: Dict
    quality_score: float  # 0-1, how well normalization succeeded
    
    def to_dict(self):
        return asdict(self)


@dataclass
class IngestionTask:
    """Task for ingesting a document"""
    task_id: str
    file_path: str
    priority: int = 1  # 1-5, higher = more important
    status: str = "pending"  # pending, processing, completed, failed
    result: Optional[ParsedDocument] = None
    error_message: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None


class DocumentParser:
    """Base class for document format parsers"""
    
    def parse(self, file_path: str) -> ParsedDocument:
        """Parse document and return normalized content"""
        raise NotImplementedError


class PlainTextParser(DocumentParser):
    """Parser for plain text files"""
    
    def parse(self, file_path: str) -> ParsedDocument:
        """Parse plain text file"""
        path = Path(file_path)
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        blocks = [
            ContentBlock(
                block_id=f"block_{idx}",
                content=line,
                content_type="text"
            )
            for idx, line in enumerate(lines) if line.strip()
        ]
        
        return ParsedDocument(
            document_id=path.stem,
            original_path=file_path,
            document_type=DocumentType.TEXT,
            content_format=ContentFormat.PLAIN_TEXT,
            blocks=blocks,
            raw_text=content,
            metadata={
                "line_count": len(lines),
                "file_size_bytes": path.stat().st_size
            }
        )


class MarkdownParser(DocumentParser):
    """Parser for Markdown files"""
    
    def parse(self, file_path: str) -> ParsedDocument:
        """Parse Markdown file with structure awareness"""
        path = Path(file_path)
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        blocks = []
        current_section = None
        
        for idx, line in enumerate(lines):
            if not line.strip():
                continue
            
            # Detect headings
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                current_section = line.lstrip('#').strip()
                blocks.append(ContentBlock(
                    block_id=f"heading_{idx}",
                    content=current_section,
                    content_type="heading",
                    level=level
                ))
            # Detect lists
            elif line.startswith('- ') or line.startswith('* '):
                blocks.append(ContentBlock(
                    block_id=f"list_item_{idx}",
                    content=line.lstrip('-* ').strip(),
                    content_type="list_item"
                ))
            # Detect code blocks
            elif line.startswith('```'):
                blocks.append(ContentBlock(
                    block_id=f"code_{idx}",
                    content=line,
                    content_type="code_fence"
                ))
            else:
                blocks.append(ContentBlock(
                    block_id=f"paragraph_{idx}",
                    content=line.strip(),
                    content_type="text"
                ))
        
        return ParsedDocument(
            document_id=path.stem,
            original_path=file_path,
            document_type=DocumentType.MARKDOWN,
            content_format=ContentFormat.MARKDOWN,
            blocks=blocks,
            raw_text=content,
            metadata={
                "line_count": len(lines),
                "heading_count": len([b for b in blocks if b.content_type == "heading"]),
                "file_size_bytes": path.stat().st_size
            }
        )


class JSONParser(DocumentParser):
    """Parser for JSON files"""
    
    def parse(self, file_path: str) -> ParsedDocument:
        """Parse JSON file"""
        path = Path(file_path)
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        blocks = []
        self._extract_json_blocks(data, blocks)
        
        return ParsedDocument(
            document_id=path.stem,
            original_path=file_path,
            document_type=DocumentType.TEXT,
            content_format=ContentFormat.JSON,
            blocks=blocks,
            raw_text=json.dumps(data, indent=2),
            metadata={
                "is_array": isinstance(data, list),
                "structure": self._analyze_json_structure(data)
            }
        )
    
    def _extract_json_blocks(self, obj, blocks, parent_key=""):
        """Recursively extract content from JSON structure"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str):
                    blocks.append(ContentBlock(
                        block_id=f"json_field_{key}",
                        content=value,
                        content_type="json_value",
                        metadata={"field": key}
                    ))
                elif isinstance(value, (list, dict)):
                    self._extract_json_blocks(value, blocks, key)
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                if isinstance(item, str):
                    blocks.append(ContentBlock(
                        block_id=f"json_array_{idx}",
                        content=item,
                        content_type="json_array_item"
                    ))
                elif isinstance(item, (dict, list)):
                    self._extract_json_blocks(item, blocks, f"{parent_key}[{idx}]")
    
    def _analyze_json_structure(self, obj):
        """Analyze JSON structure"""
        if isinstance(obj, dict):
            return {
                "type": "object",
                "keys": list(obj.keys()),
                "value_types": list(set([type(v).__name__ for v in obj.values()]))
            }
        elif isinstance(obj, list):
            return {
                "type": "array",
                "length": len(obj),
                "item_types": list(set([type(item).__name__ for item in obj]))
            }
        return {"type": "unknown"}


class MultimediaIngester:
    """
    Central ingestion system for multiple document formats
    
    Features:
    1. Support multiple document formats (text, markdown, JSON, PDF, images)
    2. Automatic format detection
    3. Normalized parsing output
    4. Batch ingestion
    5. Progress tracking
    6. Caching and deduplication
    """
    
    def __init__(self, workspace_path: str = "knowledge_workspace"):
        self.workspace = Path(workspace_path)
        self.ingest_dir = self.workspace / "ingest"
        self.ingest_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize parsers
        self.parsers = {
            DocumentType.TEXT: PlainTextParser(),
            DocumentType.MARKDOWN: MarkdownParser(),
            DocumentType.PDF: None,  # Will use OCR processor
            DocumentType.IMAGE: None,  # Will use OCR processor
        }
        
        self.parsed_documents = self._load_parsed_cache()
        self.ingest_tasks = self._load_task_cache()
        self.ocr_processor = None  # Set via set_ocr_processor
    
    def set_ocr_processor(self, processor):
        """Set OCR processor for PDF/image processing"""
        self.ocr_processor = processor
    
    def _load_parsed_cache(self) -> Dict:
        """Load cached parsed documents"""
        cache_file = self.ingest_dir / "parsed_documents.json"
        if cache_file.exists():
            with open(cache_file) as f:
                return json.load(f)
        return {}
    
    def _load_task_cache(self) -> Dict:
        """Load cached ingestion tasks"""
        cache_file = self.ingest_dir / "ingest_tasks.json"
        if cache_file.exists():
            with open(cache_file) as f:
                return json.load(f)
        return {}
    
    def _save_caches(self):
        """Persist caches"""
        # Convert enums to strings for JSON serialization
        serializable_docs = {}
        for doc_id, doc_data in self.parsed_documents.items():
            doc_copy = doc_data.copy()
            if 'document_type' in doc_copy and isinstance(doc_copy['document_type'], DocumentType):
                doc_copy['document_type'] = doc_copy['document_type'].value
            elif 'document_type' in doc_copy and isinstance(doc_copy['document_type'], str):
                pass  # Already converted
            if 'content_format' in doc_copy and hasattr(doc_copy['content_format'], 'value'):
                doc_copy['content_format'] = doc_copy['content_format'].value
            serializable_docs[doc_id] = doc_copy
        
        with open(self.ingest_dir / "parsed_documents.json", 'w') as f:
            json.dump(serializable_docs, f, indent=2)
        with open(self.ingest_dir / "ingest_tasks.json", 'w') as f:
            json.dump(self.ingest_tasks, f, indent=2)
    
    def detect_format(self, file_path: str) -> DocumentType:
        """Detect document format from file extension"""
        path = Path(file_path)
        suffix = path.suffix.lower()
        
        format_map = {
            '.txt': DocumentType.TEXT,
            '.md': DocumentType.MARKDOWN,
            '.markdown': DocumentType.MARKDOWN,
            '.json': DocumentType.TEXT,  # Use JSON parser
            '.pdf': DocumentType.PDF,
            '.png': DocumentType.IMAGE,
            '.jpg': DocumentType.IMAGE,
            '.jpeg': DocumentType.IMAGE,
            '.gif': DocumentType.IMAGE,
            '.webp': DocumentType.IMAGE,
            '.docx': DocumentType.DOCX,
            '.doc': DocumentType.DOCX,
        }
        
        return format_map.get(suffix, DocumentType.UNKNOWN)
    
    def ingest_file(self, file_path: str, ingest_id: Optional[str] = None) -> ParsedDocument:
        """
        Ingest a single file
        
        Args:
            file_path: Path to file
            ingest_id: Optional ingestion identifier
        
        Returns:
            ParsedDocument with normalized content
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        ingest_id = ingest_id or path.stem
        
        # Check cache
        if ingest_id in self.parsed_documents:
            cached = self.parsed_documents[ingest_id]
            return ParsedDocument(**cached)
        
        doc_type = self.detect_format(file_path)
        
        # Handle different format types
        if doc_type == DocumentType.MARKDOWN:
            parser = self.parsers[DocumentType.MARKDOWN]
            document = parser.parse(file_path)
        elif doc_type == DocumentType.TEXT:
            # Check if it's actually JSON
            try:
                with open(file_path) as f:
                    json.load(f)
                parser = JSONParser()
            except (json.JSONDecodeError, UnicodeDecodeError):
                parser = self.parsers[DocumentType.TEXT]
            document = parser.parse(file_path)
        elif doc_type in (DocumentType.PDF, DocumentType.IMAGE):
            if not self.ocr_processor:
                raise ValueError("OCR processor not configured for PDF/image processing")
            document = self._process_with_ocr(file_path, ingest_id, doc_type)
        else:
            raise ValueError(f"Unsupported document type: {doc_type}")
        
        # Cache result
        self.parsed_documents[ingest_id] = document.to_dict()
        self._save_caches()
        
        return document
    
    def _process_with_ocr(self, file_path: str, doc_id: str, doc_type: DocumentType) -> ParsedDocument:
        """Process file using OCR processor"""
        from backend.utils.core.ocr_processor import PDFOCRProcessor
        
        if doc_type == DocumentType.PDF:
            pdf_processor = PDFOCRProcessor(self.ocr_processor)
            results = pdf_processor.process_pdf(file_path)
            
            blocks = []
            for page_num, ocr_result in results.items():
                blocks.append(ContentBlock(
                    block_id=f"page_{page_num}",
                    content=ocr_result.extracted_text,
                    content_type="ocr_text",
                    metadata={"page": page_num, "confidence": ocr_result.confidence}
                ))
            
            return ParsedDocument(
                document_id=doc_id,
                original_path=file_path,
                document_type=doc_type,
                content_format=ContentFormat.PLAIN_TEXT,
                blocks=blocks,
                raw_text="\n".join([b.content for b in blocks]),
                metadata={"total_pages": len(results)}
            )
        else:  # Image
            result = self.ocr_processor.process_image(file_path, doc_id)
            
            blocks = [
                ContentBlock(
                    block_id=f"block_{idx}",
                    content=block["text"],
                    content_type="ocr_text",
                    metadata={"confidence": block.get("confidence", 0.9)}
                )
                for idx, block in enumerate(result.blocks)
            ]
            
            return ParsedDocument(
                document_id=doc_id,
                original_path=file_path,
                document_type=doc_type,
                content_format=ContentFormat.PLAIN_TEXT,
                blocks=blocks,
                raw_text=result.extracted_text,
                metadata={"ocr_confidence": result.confidence}
            )
    
    def ingest_batch(self, file_paths: List[str], ingest_ids: Optional[List[str]] = None) -> List[ParsedDocument]:
        """Ingest multiple files"""
        results = []
        ingest_ids = ingest_ids or [None] * len(file_paths)
        
        for file_path, ingest_id in zip(file_paths, ingest_ids):
            try:
                document = self.ingest_file(file_path, ingest_id)
                results.append(document)
            except Exception as e:
                print(f"Error ingesting {file_path}: {e}")
                continue
        
        return results
    
    def ingest_directory(self, directory_path: str) -> List[ParsedDocument]:
        """Ingest all documents in directory"""
        directory = Path(directory_path)
        if not directory.exists():
            raise ValueError(f"Directory not found: {directory_path}")
        
        results = []
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                try:
                    document = self.ingest_file(str(file_path))
                    results.append(document)
                except Exception as e:
                    print(f"Skipping {file_path}: {e}")
                    continue
        
        return results
    
    def normalize_content(self, document: ParsedDocument) -> ContentNormalization:
        """Normalize parsed document content"""
        plain_text = document.get_plain_text()
        
        # Build hierarchical structure
        structure = []
        current_section = None
        
        for block in document.blocks:
            if block.content_type == "heading":
                current_section = {
                    "title": block.content,
                    "level": block.level,
                    "subsections": []
                }
                structure.append(current_section)
            elif current_section:
                current_section["subsections"].append({
                    "type": block.content_type,
                    "content": block.content
                })
        
        # Calculate quality score (how well normalization succeeded)
        quality_score = min(1.0, len(plain_text) / 1000 * 0.5 + 0.5)
        
        return ContentNormalization(
            document_id=document.document_id,
            normalized_text=plain_text,
            structure=structure,
            metadata=document.metadata,
            quality_score=quality_score
        )
    
    def get_ingestion_stats(self) -> Dict:
        """Get ingestion statistics"""
        if not self.parsed_documents:
            return {
                "total_ingested": 0,
                "by_type": {},
                "total_blocks": 0
            }
        
        by_type = {}
        total_blocks = 0
        
        for doc in self.parsed_documents.values():
            doc_type = doc.get("document_type", "unknown")
            by_type[doc_type] = by_type.get(doc_type, 0) + 1
            total_blocks += len(doc.get("blocks", []))
        
        return {
            "total_ingested": len(self.parsed_documents),
            "by_type": by_type,
            "total_blocks": total_blocks,
            "most_recent": max(
                [doc["parsed_at"] for doc in self.parsed_documents.values()],
                default=None
            )
        }
