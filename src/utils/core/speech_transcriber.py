"""
Phase 5: Speech Transcriber
Handles audio input and transcription from Web Speech API and server-side processing
"""

import json
import base64
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from enum import Enum
import requests


class AudioFormat(Enum):
    """Supported audio formats"""
    WAV = "wav"
    MP3 = "mp3"
    OGG = "ogg"
    WEBM = "webm"
    FLAC = "flac"
    AAC = "aac"


class TranscriptionModel(Enum):
    """Available transcription models"""
    WHISPER_TINY = "whisper-tiny"
    WHISPER_BASE = "whisper-base"
    WHISPER_SMALL = "whisper-small"
    WHISPER_MEDIUM = "whisper-medium"


@dataclass
class ConfidenceSegment:
    """Speech segment with confidence score"""
    start_time_ms: float
    end_time_ms: float
    text: str
    confidence: float  # 0-1
    is_uncertain: bool = False
    
    def to_dict(self):
        return asdict(self)


@dataclass
class TranscriptionResult:
    """Result from audio transcription"""
    audio_id: str
    transcript: str
    confidence: float  # Overall confidence 0-1
    language: str = "en"
    segments: List[ConfidenceSegment] = field(default_factory=list)
    duration_seconds: float = 0.0
    processing_time_ms: float = 0.0
    model_used: str = "whisper-tiny"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        return asdict(self)
    
    def get_uncertain_segments(self) -> List[ConfidenceSegment]:
        """Get segments below confidence threshold"""
        return [s for s in self.segments if s.is_uncertain]


@dataclass
class AudioInput:
    """Audio input metadata"""
    audio_id: str
    file_path: Optional[str] = None
    format: AudioFormat = AudioFormat.WAV
    duration_seconds: float = 0.0
    sample_rate_hz: int = 16000
    channels: int = 1
    size_bytes: int = 0
    source: str = "file"  # "file", "microphone", "stream"
    
    def to_dict(self):
        return asdict(self)


@dataclass
class TranscriptionConfig:
    """Configuration for transcription"""
    ollama_host: str = "http://localhost:11434"
    model_name: str = "whisper-tiny"  # Fast, can use tiny/base/small/medium
    language: str = "en"
    temperature: float = 0.0
    timeout_seconds: int = 300
    min_confidence: float = 0.7  # Threshold for "uncertain" segments
    
    def to_dict(self):
        return asdict(self)


class SpeechTranscriber:
    """
    Handles audio transcription and speech-to-text conversion
    
    Features:
    1. Transcribe audio files (WAV, MP3, OGG, WEBM, FLAC, AAC)
    2. Stream transcription for long audio
    3. Confidence scoring for segments
    4. Language detection
    5. Efficient processing with caching
    6. Integration with Web Speech API results
    """
    
    def __init__(self, workspace_path: str = "knowledge_workspace", config: Optional[TranscriptionConfig] = None):
        self.workspace = Path(workspace_path)
        self.speech_dir = self.workspace / "speech"
        self.speech_dir.mkdir(parents=True, exist_ok=True)
        
        self.config = config or TranscriptionConfig()
        self.results_cache = self.speech_dir / "transcriptions.json"
        self.transcriptions = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load previously transcribed audio"""
        if self.results_cache.exists():
            with open(self.results_cache) as f:
                return json.load(f)
        return {}
    
    def _save_cache(self):
        """Persist transcription results"""
        with open(self.results_cache, 'w') as f:
            json.dump(self.transcriptions, f, indent=2)
    
    def _validate_audio(self, audio_path: str) -> bool:
        """Validate audio file"""
        path = Path(audio_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # Check format
        suffix = path.suffix.lstrip('.').lower()
        try:
            audio_format = AudioFormat[suffix.upper()]
        except KeyError:
            raise ValueError(f"Unsupported audio format: {suffix}")
        
        # Check size (limit to 100MB for practical reasons)
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > 100:
            raise ValueError(f"Audio file too large: {size_mb}MB (max: 100MB)")
        
        return True
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """Estimate audio duration from file size"""
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0  # Convert milliseconds to seconds
        except ImportError:
            # Fallback: estimate based on file size
            # Assuming 16-bit mono at 16kHz
            size = Path(audio_path).stat().st_size
            return size / (16000 * 2)
    
    def transcribe_audio(self, audio_path: str, audio_id: Optional[str] = None) -> TranscriptionResult:
        """
        Transcribe audio file using Ollama Whisper model
        
        Args:
            audio_path: Path to audio file
            audio_id: Optional unique identifier
        
        Returns:
            TranscriptionResult with transcript and confidence
        """
        # Validate audio
        self._validate_audio(audio_path)
        
        if not audio_id:
            audio_id = Path(audio_path).stem
        
        # Check cache
        if audio_id in self.transcriptions:
            cached = self.transcriptions[audio_id]
            return TranscriptionResult(**cached)
        
        # Get audio duration
        try:
            duration = self._get_audio_duration(audio_path)
        except Exception:
            duration = 0.0
        
        # Process with Ollama
        try:
            result = self._call_ollama_transcribe(audio_path, audio_id, duration)
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.config.ollama_host}. "
                f"Make sure Ollama is running: ollama serve"
            )
        
        # Cache result
        self.transcriptions[audio_id] = result.to_dict()
        self._save_cache()
        
        return result
    
    def _call_ollama_transcribe(self, audio_path: str, audio_id: str, duration_seconds: float) -> TranscriptionResult:
        """Call Whisper model via Ollama for transcription"""
        import time
        start_time = time.time()
        
        # Read and encode audio
        with open(audio_path, 'rb') as f:
            audio_data = base64.b64encode(f.read()).decode('utf-8')
        
        url = f"{self.config.ollama_host}/api/generate"
        
        prompt = "Transcribe this audio. Return only the transcript text."
        
        payload = {
            "model": self.config.model_name,
            "prompt": prompt,
            "images": [audio_data],  # Ollama API accepts binary data as images field
            "stream": False,
            "temperature": self.config.temperature,
        }
        
        try:
            response = requests.post(url, json=payload, timeout=self.config.timeout_seconds)
            response.raise_for_status()
            
            data = response.json()
            transcript = data.get("response", "").strip()
            
            processing_time = (time.time() - start_time) * 1000
            
            # Parse segments from transcript
            segments = self._parse_segments(transcript)
            
            # Calculate overall confidence
            confidence = self._calculate_confidence(segments)
            
            return TranscriptionResult(
                audio_id=audio_id,
                transcript=transcript,
                confidence=confidence,
                duration_seconds=duration_seconds,
                processing_time_ms=processing_time,
                segments=segments,
                model_used=self.config.model_name
            )
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama transcription error: {e}")
    
    def _parse_segments(self, transcript: str) -> List[ConfidenceSegment]:
        """Parse transcript into segments with confidence"""
        segments = []
        
        # Split by sentences (simplified)
        sentences = transcript.split('. ')
        
        # Estimate timing (naive approach: equal distribution)
        total_segments = len(sentences)
        
        for idx, sentence in enumerate(sentences):
            if not sentence.strip():
                continue
            
            # Estimate confidence based on sentence completeness
            confidence = self._estimate_segment_confidence(sentence)
            
            segment = ConfidenceSegment(
                start_time_ms=(idx / total_segments) * 1000,
                end_time_ms=((idx + 1) / total_segments) * 1000,
                text=sentence.strip(),
                confidence=confidence,
                is_uncertain=confidence < 0.7
            )
            segments.append(segment)
        
        return segments
    
    def _estimate_segment_confidence(self, text: str) -> float:
        """Estimate confidence score for a segment"""
        if not text.strip():
            return 0.0
        
        # Heuristics for confidence
        confidence = 0.9
        
        # Penalize very short segments
        if len(text.split()) < 2:
            confidence -= 0.2
        
        # Penalize unusual characters
        if any(ord(c) > 127 for c in text):
            confidence -= 0.1
        
        # Penalize all caps (often misrecognized)
        if text.isupper():
            confidence -= 0.1
        
        return max(0.0, min(1.0, confidence))
    
    def _calculate_confidence(self, segments: List[ConfidenceSegment]) -> float:
        """Calculate overall confidence from segments"""
        if not segments:
            return 0.0
        
        avg_confidence = sum(s.confidence for s in segments) / len(segments)
        return avg_confidence
    
    def stream_transcription(self, audio_path: str, chunk_duration_ms: int = 1000) -> List[TranscriptionResult]:
        """
        Stream transcription by processing audio in chunks
        
        Args:
            audio_path: Path to audio file
            chunk_duration_ms: Duration of each chunk in milliseconds
        
        Returns:
            List of TranscriptionResults for each chunk
        """
        try:
            from pydub import AudioSegment
            from pydub.utils import mediainfo
        except ImportError:
            raise ImportError("pydub not installed. Install with: pip install pydub")
        
        # Load audio
        audio = AudioSegment.from_file(audio_path)
        
        # Split into chunks
        chunks = []
        for start_ms in range(0, len(audio), chunk_duration_ms):
            end_ms = min(start_ms + chunk_duration_ms, len(audio))
            chunk = audio[start_ms:end_ms]
            
            # Save chunk temporarily
            temp_chunk_path = self.speech_dir / f"temp_chunk_{start_ms}.wav"
            chunk.export(str(temp_chunk_path), format="wav")
            chunks.append(str(temp_chunk_path))
        
        # Transcribe each chunk
        results = []
        for idx, chunk_path in enumerate(chunks):
            try:
                chunk_id = f"{Path(audio_path).stem}_chunk_{idx}"
                result = self.transcribe_audio(chunk_path, chunk_id)
                results.append(result)
            finally:
                # Clean up temp chunk
                Path(chunk_path).unlink()
        
        return results
    
    def integrate_web_speech_result(self, audio_id: str, web_speech_transcript: str, web_speech_confidence: float) -> TranscriptionResult:
        """
        Integrate transcription result from Web Speech API
        
        Args:
            audio_id: Audio identifier
            web_speech_transcript: Transcript from Web Speech API
            web_speech_confidence: Confidence from Web Speech API
        
        Returns:
            TranscriptionResult with integrated result
        """
        # Parse segments from web speech result
        segments = self._parse_segments(web_speech_transcript)
        
        # Create result
        result = TranscriptionResult(
            audio_id=audio_id,
            transcript=web_speech_transcript,
            confidence=web_speech_confidence,
            segments=segments,
            model_used="web-speech-api"
        )
        
        # Cache result
        self.transcriptions[audio_id] = result.to_dict()
        self._save_cache()
        
        return result
    
    def match_confidence_thresholds(self, result: TranscriptionResult, threshold: float = 0.7) -> Dict:
        """
        Analyze which segments meet confidence threshold
        
        Args:
            result: TranscriptionResult
            threshold: Confidence threshold
        
        Returns:
            Dict with analysis
        """
        above_threshold = [s for s in result.segments if s.confidence >= threshold]
        below_threshold = result.get_uncertain_segments()
        
        return {
            "total_segments": len(result.segments),
            "above_threshold_count": len(above_threshold),
            "below_threshold_count": len(below_threshold),
            "above_threshold_text": " ".join([s.text for s in above_threshold]),
            "below_threshold_text": " ".join([s.text for s in below_threshold]),
            "confidence_ratio": len(above_threshold) / len(result.segments) if result.segments else 0
        }
    
    def get_transcript_summary(self, result: TranscriptionResult) -> Dict:
        """
        Generate summary of transcription
        
        Args:
            result: TranscriptionResult
        
        Returns:
            Dict with summary statistics
        """
        word_count = len(result.transcript.split())
        
        return {
            "audio_id": result.audio_id,
            "transcript_length": len(result.transcript),
            "word_count": word_count,
            "segment_count": len(result.segments),
            "overall_confidence": result.confidence,
            "uncertain_segments": len(result.get_uncertain_segments()),
            "duration_seconds": result.duration_seconds,
            "processing_time_ms": result.processing_time_ms,
            "wpm": (word_count / result.duration_seconds) if result.duration_seconds > 0 else 0
        }
    
    def get_transcription_stats(self) -> Dict:
        """Get transcription statistics"""
        if not self.transcriptions:
            return {
                "total_transcribed": 0,
                "avg_confidence": 0,
                "total_words": 0,
                "total_duration_seconds": 0
            }
        
        transcriptions = list(self.transcriptions.values())
        confidences = [t["confidence"] for t in transcriptions]
        words = [len(t["transcript"].split()) for t in transcriptions]
        durations = [t["duration_seconds"] for t in transcriptions]
        
        return {
            "total_transcribed": len(transcriptions),
            "avg_confidence": sum(confidences) / len(confidences) if confidences else 0,
            "total_words": sum(words),
            "total_duration_seconds": sum(durations),
            "most_recent": max(
                [t["timestamp"] for t in transcriptions],
                default=None
            )
        }
    
    def clear_cache(self):
        """Clear transcription cache"""
        self.transcriptions = {}
        if self.results_cache.exists():
            self.results_cache.unlink()
