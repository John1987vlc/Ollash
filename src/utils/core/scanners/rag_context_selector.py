"""RAG-based Context Selection using semantic similarity.

This module leverages ChromaDB and all-minilm embeddings to select
the most relevant code fragments for a given task, optimizing for
limited context windows (e.g., 4096 tokens).

Design: Replaces heuristic file/directory selection with semantic search.
Benefit: Sends only relevant fragments instead of entire files.
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import chromadb
from chromadb.config import Settings

from src.utils.core.agent_logger import AgentLogger
from src.utils.core.token_tracker import TokenTracker


class CodeFragment:
    """Represents a chunk of code with metadata."""

    def __init__(
        self,
        file_path: str,
        language: str,
        content: str,
        start_line: int = 1,
        end_line: Optional[int] = None,
        is_synthetic: bool = False,
    ):
        self.file_path = file_path
        self.language = language
        self.content = content
        self.start_line = start_line
        self.end_line = end_line or (start_line + len(content.splitlines()))
        self.is_synthetic = is_synthetic  # Generated or analyzed content

    def to_dict(self) -> Dict:
        return {
            "file_path": self.file_path,
            "language": self.language,
            "content": self.content,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "is_synthetic": self.is_synthetic,
        }


class RAGContextSelector:
    """Semantic context selection using embeddings."""

    def __init__(
        self,
        project_root: Path,
        logger: AgentLogger,
        max_context_tokens: int = 4096,
        overlap_fraction: float = 0.6,  # Cosine similarity threshold
    ):
        self.project_root = project_root
        self.logger = logger

        self.max_context_tokens = max_context_tokens
        self.overlap_fraction = overlap_fraction
        
        # Initialize ChromaDB client
        self.db_path = project_root / ".ollash" / "chroma_db"
        self.db_path.mkdir(parents=True, exist_ok=True)
        
        settings = Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=str(self.db_path),
            anonymized_telemetry=False,
        )
        self.client = chromadb.Client(settings)
        self.collection = self.client.get_or_create_collection(
            name="code_fragments",
            metadata={"hnsw:space": "cosine"},
        )

    def index_code_fragments(self, files: Dict[str, str]):
        """Index all code fragments from project files for semantic search."""
        self.logger.info(f"📚 Indexing {len(files)} files for semantic search...")
        
        fragments: List[CodeFragment] = []
        
        for file_path, content in files.items():
            language = self._detect_language(file_path)
            
            # Split file into chunks (e.g., 20-50 lines per fragment)
            lines = content.splitlines()
            chunk_size = 30
            
            for i in range(0, len(lines), chunk_size):
                chunk = "\n".join(lines[i : i + chunk_size])
                fragment = CodeFragment(
                    file_path=file_path,
                    language=language,
                    content=chunk,
                    start_line=i + 1,
                    end_line=min(i + chunk_size, len(lines)),
                )
                fragments.append(fragment)
        
        # Store fragments in ChromaDB
        ids = []
        documents = []
        metadatas = []
        
        for idx, fragment in enumerate(fragments):
            ids.append(f"frag_{idx}")
            documents.append(fragment.content)
            metadatas.append(
                {
                    "file_path": fragment.file_path,
                    "language": fragment.language,
                    "start_line": str(fragment.start_line),
                    "end_line": str(fragment.end_line),
                }
            )
        
        if ids:
            self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
            self.logger.info(
                f"  ✅ Indexed {len(fragments)} code fragments across {len(files)} files"
            )

    def select_relevant_fragments(
        self,
        task_description: str,
        num_fragments: int = 5,
    ) -> List[CodeFragment]:
        """Select most relevant code fragments using semantic similarity."""
        if self.collection.count() == 0:
            self.logger.warning("No indexed fragments found")
            return []

        # Query the collection for similar fragments
        results = self.collection.query(
            query_texts=[task_description],
            n_results=min(num_fragments, self.collection.count()),
        )

        fragments = []
        if results and results["ids"] and results["ids"][0]:
            for i, frag_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i]
                content = results["documents"][0][i]
                
                fragment = CodeFragment(
                    file_path=metadata["file_path"],
                    language=metadata["language"],
                    content=content,
                    start_line=int(metadata["start_line"]),
                    end_line=int(metadata["end_line"]),
                )
                fragments.append(fragment)

        self.logger.info(
            f"  Selected {len(fragments)} fragments for task: '{task_description[:50]}...'"
        )
        return fragments

    def build_context(
        self,
        task_description: str,
        required_files: Optional[List[str]] = None,
    ) -> Tuple[str, int]:
        """Build optimized context string from relevant fragments.
        
        Returns:
            Tuple of (context_string, token_count)
        """
        context_parts = []
        token_count = 0

        # 1. Always include explicitly required files
        if required_files:
            for file_path in required_files:
                full_path = self.project_root / file_path
                if full_path.exists():
                    content = full_path.read_text()
                    tokens = self._estimate_tokens(content)
                    if token_count + tokens < self.max_context_tokens:
                        context_parts.append(f"# {file_path}\n{content}")
                        token_count += tokens

        # 2. Add relevant semantic fragments
        fragments = self.select_relevant_fragments(task_description)
        for fragment in fragments:
            tokens = self._estimate_tokens(fragment.content)
            if token_count + tokens < self.max_context_tokens:
                header = (
                    f"# {fragment.file_path} (lines {fragment.start_line}-{fragment.end_line})"
                )
                context_parts.append(f"{header}\n{fragment.content}")
                token_count += tokens + 10  # Include header tokens

        context = "\n\n---\n\n".join(context_parts)
        return context, token_count

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for a given text using a simple heuristic."""
        # This is a basic heuristic; a more accurate one would use a tokenizer
        return len(text) // 4 # Average 4 chars per token for English text

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "jsx",
            ".tsx": "tsx",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".cpp": "cpp",
            ".c": "c",
            ".rb": "ruby",
            ".php": "php",
            ".sh": "bash",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".xml": "xml",
            ".html": "html",
            ".css": "css",
            ".sql": "sql",
        }
        return mapping.get(ext, "text")

    def clear_index(self):
        """Clear the fragment index."""
        self.client.delete_collection(name="code_fragments")
        self.collection = self.client.get_or_create_collection(
            name="code_fragments",
            metadata={"hnsw:space": "cosine"},
        )
        self.logger.info("Cleared code fragment index")


class SemanticContextManager:
    """High-level manager for semantic context selection in multi-phase tasks."""

    def __init__(
        self,
        project_root: Path,
        logger: AgentLogger,
    ):
        self.project_root = project_root
        self.logger = logger
        self.selector = RAGContextSelector(
            project_root=project_root,
            logger=logger,
        )

    def prepare_context_for_phase(
        self,
        phase_name: str,
        task_description: str,
        files: Dict[str, str],
        required_files: Optional[List[str]] = None,
    ) -> Tuple[str, Dict]:
        """Prepare context for a specific pipeline phase.
        
        Returns:
            Tuple of (context_string, metadata)
        """
        # Index all files for this phase
        self.selector.index_code_fragments(files)

        # Build optimized context
        context, tokens = self.selector.build_context(
            task_description=task_description,
            required_files=required_files,
        )

        metadata = {
            "phase": phase_name,
            "context_tokens": tokens,
            "max_tokens": self.selector.max_context_tokens,
            "fragments_indexed": self.selector.collection.count(),
        }

        self.logger.info(
            f"  📖 Phase '{phase_name}': {tokens}/{self.selector.max_context_tokens} tokens used"
        )

        return context, metadata
