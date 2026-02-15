"""
Cascade Summarizer - Map-Reduce pattern for processing long documents.
Splits text into chunks, summarizes each individually, then creates a master summary.
"""

from typing import List, Dict, Optional
from pathlib import Path

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.ollama_client import OllamaClient


class CascadeSummarizer:
    """
    Implements a hierarchical summarization strategy:
    1. Map phase: Split document into chunks and summarize each
    2. Reduce phase: Summarize the collection of summaries

    This allows processing of very long documents without hitting token limits.
    """

    def __init__(
        self,
        ollama_client: OllamaClient,
        logger: AgentLogger,
        config: Optional[Dict] = None,
    ):
        self.ollama = ollama_client
        self.logger = logger
        self.config = config or {}
        self.chunk_size = self.config.get("cascade_chunk_size", 2000)  # words
        self.overlap = self.config.get("cascade_overlap", 300)  # words

    def chunk_text(self, text: str, chunk_size: int = None, overlap: int = None) -> List[str]:
        """Splits text into overlapping chunks by word count."""
        chunk_size = chunk_size or self.chunk_size
        overlap = overlap or self.overlap

        words = text.split()
        if not words:
            return []

        chunks = []
        step = max(1, chunk_size - overlap)  # Avoid infinite loop

        i = 0
        while i < len(words):
            chunk_words = words[i : i + chunk_size]
            chunks.append(" ".join(chunk_words))
            i += step

        return chunks

    def summarize_chunk(self, chunk_text: str, context: str = "") -> Optional[str]:
        """Summarizes a single chunk of text using the summarizer model."""
        prompt = f"""You are an expert technical summarizer.
Distill the following text into its key points and main ideas concisely.
Focus on facts, not verbosity.

Text to summarize:
{chunk_text}

{f"Context: {context}" if context else ""}

Provide a clear, concise summary (50-150 words):"""

        try:
            response = self.ollama.call_ollama_api(
                model="ministral-3:8b",  # Fast summarizer
                prompt=prompt,
                temperature=0.3,
                max_tokens=500,
            )
            return response.strip() if response else None
        except Exception as e:
            self.logger.error(f"Chunk summarization failed: {e}")
            return None

    def map_phase(self, text: str) -> Dict[int, str]:
        """
        Map phase: Chunks the document and summarizes each chunk.
        Returns dict: {chunk_index: summary}
        """
        chunks = self.chunk_text(text)
        if not chunks:
            self.logger.warning("No chunks generated from text")
            return {}

        summaries = {}
        for i, chunk in enumerate(chunks):
            summary = self.summarize_chunk(chunk)
            if summary:
                summaries[i] = summary
                self.logger.debug(f"  Summarized chunk {i + 1}/{len(chunks)}")
            else:
                # If summarization fails, keep original chunk
                summaries[i] = chunk[:500]  # Truncate very long chunks

        self.logger.info(f"✓ Map phase complete: {len(summaries)} chunk summaries")
        return summaries

    def reduce_phase(self, chunk_summaries: Dict[int, str], title: str = "") -> Optional[str]:
        """
        Reduce phase: Combines chunk summaries into a final master summary.
        """
        if not chunk_summaries:
            return None

        # Combine all summaries
        combined = "\n\n".join(chunk_summaries.values())

        prompt = f"""You are an expert technical writer.
Review the following individual section summaries and create a unified,
comprehensive executive summary that captures the key themes, insights, and findings.

Document: {title}

Section summaries:
{combined}

Create a well-structured executive summary (100-300 words) with:
- Key findings
- Main themes
- Critical insights
- Recommendations (if applicable)

Executive Summary:"""

        try:
            response = self.ollama.call_ollama_api(
                model="ministral-3:14b",  # Better quality for final summary
                prompt=prompt,
                temperature=0.2,
                max_tokens=1000,
            )
            return response.strip() if response else None
        except Exception as e:
            self.logger.error(f"Reduce phase failed: {e}")
            return None

    def cascade_summarize(self, text: str, title: str = "") -> Dict[str, any]:
        """
        Full cascade summarization pipeline.
        Returns: {
            status: "success|error",
            title: str,
            original_word_count: int,
            chunk_count: int,
            chunk_summaries: {chunk_id: summary},
            executive_summary: str,
            compression_ratio: float
        }
        """
        original_words = len(text.split())

        self.logger.info(f"🔄 Starting cascade summarization for {title or 'document'}")
        self.logger.info(f"   Original length: {original_words} words")

        # Map phase
        chunk_summaries = self.map_phase(text)
        if not chunk_summaries:
            return {
                "status": "error",
                "message": "Failed to generate chunk summaries",
            }

        # Reduce phase
        executive_summary = self.reduce_phase(chunk_summaries, title)
        if not executive_summary:
            return {
                "status": "error",
                "message": "Failed to generate executive summary",
            }

        summary_words = len(executive_summary.split())
        compression_ratio = original_words / summary_words if summary_words > 0 else 0

        self.logger.info("✅ Cascade summarization complete")
        self.logger.info(f"   Final summary: {summary_words} words (ratio: {compression_ratio:.1f}:1)")

        return {
            "status": "success",
            "title": title,
            "original_word_count": original_words,
            "chunk_count": len(chunk_summaries),
            "chunk_summaries": chunk_summaries,
            "executive_summary": executive_summary,
            "compression_ratio": compression_ratio,
        }

    def save_summary(self, summary_result: Dict, output_dir: Path):
        """Saves cascade summary results to file."""
        if summary_result.get("status") != "success":
            self.logger.warning("Cannot save failed summary result")
            return

        output_dir.mkdir(parents=True, exist_ok=True)

        # Save as JSON
        json_path = output_dir / f"{summary_result['title']}_summary.json"
        import json
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(summary_result, f, indent=2, ensure_ascii=False)

        # Save as readable text
        text_path = output_dir / f"{summary_result['title']}_summary.txt"
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(f"Executive Summary: {summary_result['title']}\n")
            f.write("=" * 80 + "\n\n")
            f.write(summary_result["executive_summary"])
            f.write("\n\n" + "=" * 80 + "\n")
            f.write(f"Original: {summary_result['original_word_count']} words\n")
            f.write(f"Summary: {len(summary_result['executive_summary'].split())} words\n")
            f.write(f"Compression: {summary_result['compression_ratio']:.1f}:1\n")

        self.logger.info(f"💾 Summary saved to {output_dir}")

