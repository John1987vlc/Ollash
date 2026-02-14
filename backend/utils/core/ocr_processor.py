"""
Phase 5: OCR Processor
Handles optical character recognition using deepseek-ocr:3b model via Ollama
"""

import json
import base64
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import requests
from enum import Enum


class ImageFormat(Enum):
    """Supported image formats"""
    PNG = "png"
    JPG = "jpeg"
    PDF = "pdf"
    WEBP = "webp"


@dataclass
class OCRResult:
    """Result from OCR processing"""
    image_id: str
    extracted_text: str
    confidence: float  # 0-1, how confident the OCR is
    detected_language: str = "en"
    processing_time_ms: float = 0.0
    blocks: List[Dict] = field(default_factory=list)  # Text blocks with coordinates
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        return asdict(self)


@dataclass
class OCRConfig:
    """Configuration for OCR processing"""
    ollama_host: str = "http://localhost:11434"
    model_name: str = "deepseek-ocr:3b"
    temperature: float = 0.0  # Deterministic for OCR
    timeout_seconds: int = 120
    max_image_size_mb: int = 50
    supported_formats: List[str] = field(default_factory=lambda: ["png", "jpg", "jpeg", "pdf", "webp"])
    
    def to_dict(self):
        return asdict(self)


class OCRProcessor:
    """
    Handles optical character recognition for images and PDFs
    
    Features:
    1. Extract text from images (PNG, JPG, PDF, WebP)
    2. Detect text regions and coordinates
    3. Estimate confidence scores
    4. Support batch processing
    5. Cache results locally
    """
    
    def __init__(self, workspace_path: str = "knowledge_workspace", config: Optional[OCRConfig] = None):
        self.workspace = Path(workspace_path)
        self.ocr_dir = self.workspace / "ocr"
        self.ocr_dir.mkdir(parents=True, exist_ok=True)
        
        self.config = config or OCRConfig()
        self.results_cache = self.ocr_dir / "ocr_results.json"
        self.processed_images = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load previously processed images"""
        if self.results_cache.exists():
            with open(self.results_cache) as f:
                return json.load(f)
        return {}
    
    def _save_cache(self):
        """Persist processed results"""
        with open(self.results_cache, 'w') as f:
            json.dump(self.processed_images, f, indent=2)
    
    def _encode_image_to_base64(self, image_path: str) -> str:
        """Encode image file to base64 for API"""
        try:
            with open(image_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to encode image: {e}")
    
    def _validate_image(self, image_path: str) -> bool:
        """Validate image file existenceand format"""
        path = Path(image_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        # Check format
        suffix = path.suffix.lstrip('.').lower()
        if suffix not in self.config.supported_formats:
            raise ValueError(f"Unsupported format: {suffix}. Supported: {self.config.supported_formats}")
        
        # Check size
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.config.max_image_size_mb:
            raise ValueError(f"Image too large: {size_mb}MB (max: {self.config.max_image_size_mb}MB)")
        
        return True
    
    def process_image(self, image_path: str, image_id: Optional[str] = None) -> OCRResult:
        """
        Process an image and extract text using deepseek-ocr:3b
        
        Args:
            image_path: Path to image file
            image_id: Optional unique identifier (default: filename hash)
        
        Returns:
            OCRResult with extracted text and metadata
        """
        # Validate image
        self._validate_image(image_path)
        
        # Generate image ID if not provided
        if not image_id:
            image_id = Path(image_path).stem
        
        # Check cache
        if image_id in self.processed_images:
            cached = self.processed_images[image_id]
            return OCRResult(**cached)
        
        # Encode image
        image_data = self._encode_image_to_base64(image_path)
        
        # Call Ollama OCR model
        try:
            result = self._call_ollama_ocr(image_data, image_id)
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.config.ollama_host}. "
                f"Make sure Ollama is running: ollama serve"
            )
        
        # Cache result
        self.processed_images[image_id] = result.to_dict()
        self._save_cache()
        
        return result
    
    def _call_ollama_ocr(self, image_base64: str, image_id: str) -> OCRResult:
        """Call deepseek-ocr:3b model via Ollama"""
        import time
        start_time = time.time()
        
        # Prepare request to Ollama
        url = f"{self.config.ollama_host}/api/generate"
        
        # Ollama expects image in base64 format with data: prefix
        prompt = "Extract all text from this image. List each line separately."
        
        payload = {
            "model": self.config.model_name,
            "prompt": prompt,
            "images": [image_base64],
            "stream": False,
            "temperature": self.config.temperature,
        }
        
        try:
            response = requests.post(url, json=payload, timeout=self.config.timeout_seconds)
            response.raise_for_status()
            
            data = response.json()
            extracted_text = data.get("response", "")
            
            processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Parse response to detect blocks and confidence
            blocks = self._parse_text_blocks(extracted_text)
            
            # Estimate confidence (simplified: full response = high confidence)
            confidence = min(1.0, len(extracted_text.split()) / 100)
            
            return OCRResult(
                image_id=image_id,
                extracted_text=extracted_text,
                confidence=confidence,
                processing_time_ms=processing_time,
                blocks=blocks
            )
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama API error: {e}")
    
    def _parse_text_blocks(self, text: str) -> List[Dict]:
        """Parse extracted text into blocks"""
        blocks = []
        for idx, line in enumerate(text.split('\n')):
            if line.strip():
                blocks.append({
                    "block_id": idx,
                    "text": line.strip(),
                    "confidence": 0.9
                })
        return blocks
    
    def process_batch(self, image_paths: List[str], image_ids: Optional[List[str]] = None) -> List[OCRResult]:
        """
        Process multiple images
        
        Args:
            image_paths: List of image file paths
            image_ids: Optional list of image identifiers
        
        Returns:
            List of OCRResults
        """
        results = []
        image_ids = image_ids or [None] * len(image_paths)
        
        for image_path, image_id in zip(image_paths, image_ids):
            try:
                result = self.process_image(image_path, image_id)
                results.append(result)
            except Exception as e:
                # Log error but continue processing
                print(f"Error processing {image_path}: {e}")
                continue
        
        return results
    
    def extract_text_from_directory(self, directory_path: str, pattern: str = "*.png") -> Dict[str, str]:
        """
        Process all images in a directory
        
        Args:
            directory_path: Path to directory containing images
            pattern: File pattern to match (default: *.png)
        
        Returns:
            Dict mapping image IDs to extracted text
        """
        directory = Path(directory_path)
        if not directory.exists():
            raise ValueError(f"Directory not found: {directory_path}")
        
        image_files = list(directory.glob(pattern))
        results = self.process_batch([str(f) for f in image_files])
        
        return {result.image_id: result.extracted_text for result in results}
    
    def get_processing_stats(self) -> Dict:
        """Get OCR processing statistics"""
        if not self.processed_images:
            return {
                "total_processed": 0,
                "avg_confidence": 0,
                "avg_processing_time_ms": 0
            }
        
        confidences = [img["confidence"] for img in self.processed_images.values()]
        times = [img["processing_time_ms"] for img in self.processed_images.values()]
        
        return {
            "total_processed": len(self.processed_images),
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
            "avg_processing_time_ms": sum(times) / len(times) if times else 0,
            "most_recent": max(
                [img["timestamp"] for img in self.processed_images.values()],
                default=None
            )
        }
    
    def clear_cache(self):
        """Clear OCR results cache"""
        self.processed_images = {}
        if self.results_cache.exists():
            self.results_cache.unlink()


class PDFOCRProcessor:
    """
    Special handling for PDF files - extracts and processes each page
    """
    
    def __init__(self, ocr_processor: OCRProcessor):
        self.ocr = ocr_processor
    
    def process_pdf(self, pdf_path: str) -> Dict[int, OCRResult]:
        """
        Process PDF file page by page
        Note: Requires pdf2image library for conversion
        
        Args:
            pdf_path: Path to PDF file
        
        Returns:
            Dict mapping page numbers to OCRResults
        """
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError("pdf2image not installed. Install with: pip install pdf2image")
        
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        # Convert PDF to images
        images = convert_from_path(str(pdf_path), dpi=300)
        
        results = {}
        for page_num, image in enumerate(images, start=1):
            # Save temporary image
            temp_image_path = self.ocr.ocr_dir / f"temp_page_{page_num}.png"
            image.save(str(temp_image_path), 'PNG')
            
            # Process with OCR
            image_id = f"{pdf_path.stem}_page_{page_num}"
            result = self.ocr.process_image(str(temp_image_path), image_id)
            results[page_num] = result
            
            # Clean up temp image
            temp_image_path.unlink()
        
        return results
