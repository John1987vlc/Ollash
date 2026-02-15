import os
from pathlib import Path
from typing import Dict, List, Any, Optional

from backend.utils.core.ollama_client import OllamaClient
from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.multi_format_ingester import MultiFormatIngester
from backend.utils.core.chroma_manager import ChromaClientManager


class DocumentationManager:
    def __init__(self, project_root: Path, logger: AgentLogger, llm_recorder: Any, config: Optional[Dict] = None):
        self.project_root = project_root
        self.logger = logger
        self.config = config or {}
        self.llm_recorder = llm_recorder # Store llm_recorder

        # Knowledge workspace paths
        self.knowledge_workspace = project_root / "knowledge_workspace"
        self.references_dir = self.knowledge_workspace / "references"
        self.summaries_dir = self.knowledge_workspace / "summaries"
        self.indexed_cache = self.knowledge_workspace / "indexed_cache"
        
        # Ensure directories exist
        self.references_dir.mkdir(parents=True, exist_ok=True)
        self.summaries_dir.mkdir(parents=True, exist_ok=True)
        self.indexed_cache.mkdir(parents=True, exist_ok=True)

        self.chroma_client = ChromaClientManager.get_client(self.config, self.project_root)
        self.documentation_collection = self.chroma_client.get_or_create_collection(name="documentation_store")

        # Embedding client - reuse or create new
        # Create a consolidated config dictionary for OllamaClient
        ollama_client_config_dict = {
            "ollama_max_retries": self.config.get("ollama_max_retries", 5),
            "ollama_backoff_factor": self.config.get("ollama_backoff_factor", 1.0),
            "ollama_retry_status_forcelist": self.config.get("ollama_retry_status_forcelist", [429, 500, 502, 503, 504]),
            "embedding_cache": self.config.get("embedding_cache", {}),
            "project_root": str(self.project_root), # Pass project_root as string
            "ollama_embedding_model": self.config.get("ollama_embedding_model", "all-minilm"),
        }
        ollama_url = os.environ.get("OLLASH_OLLAMA_URL", self.config.get("ollama_url", "http://localhost:11434"))
        ollama_timeout = self.config.get("timeout", 300) # Extract timeout here
        self.embedding_client = OllamaClient(
            url=ollama_url,
            model=self.config.get("embedding", "all-minilm"), # Get embedding model from config
            timeout=ollama_timeout, # Pass as positional argument
            logger=self.logger,
            config=ollama_client_config_dict,
            llm_recorder=self.llm_recorder # Pass llm_recorder here
        )

        # Multi-format ingester
        self.ingester = MultiFormatIngester(logger, config)

        self.logger.info("✓ DocumentationManager initialized with Knowledge Workspace support")

    def index_documentation(self, doc_path: Path, chunk_size: int = 1000, overlap: int = 200):
        """Index documentation files with support for multiple formats."""
        try:
            file_path = Path(doc_path)
            if not file_path.exists():
                self.logger.warning(f"Documentation file not found: {file_path}")
                return

            # Use multi-format ingester for binary files (PDF, DOCX, etc.)
            if file_path.suffix.lower() in self.ingester.SUPPORTED_FORMATS:
                content = self.ingester.ingest_file(file_path)
                if not content:
                    self.logger.warning(f"  Could not extract content from {file_path.name}")
                    return
            else:
                # Fallback to plain text read for unsupported formats
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            
            chunks = self._chunk_text(content, chunk_size, overlap)
            
            embeddings = []
            metadatas = []
            ids = []

            for i, chunk in enumerate(chunks):
                embedding = self.embedding_client.get_embedding(chunk)
                embeddings.append(embedding)
                try:
                    source_rel = str(file_path.relative_to(self.project_root))
                except ValueError:
                    source_rel = str(file_path)
                
                metadatas.append({
                    "source": source_rel,
                    "chunk_index": i,
                    "file_format": file_path.suffix.lower()
                })
                ids.append(f"{file_path.stem}-{i}")
            
            if embeddings:
                self.documentation_collection.add(
                    embeddings=embeddings,
                    documents=chunks,
                    metadatas=metadatas,
                    ids=ids
                )
                self.logger.info(f"  ✓ Indexed {len(chunks)} chunks from {file_path.name}")
        except Exception as e:
            self.logger.error(f"  Failed to index {file_path.name}: {e}")

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Splits text into overlapping chunks."""
        chunks = []
        words = text.split()
        if not words:
            return chunks

        i = 0
        while i < len(words):
            chunk_words = words[i : i + chunk_size]
            chunks.append(" ".join(chunk_words))
            i += (chunk_size - overlap)
            if i < 0: # Handle cases where chunk_size < overlap
                i = 0
            
        return chunks

    def query_documentation(self, query: str, n_results: int = 3, min_distance: float = 0.5) -> List[Dict]:
        """
        Queries the indexed documentation for relevant snippets.
        Returns a list of dictionaries, each with 'document', 'source', 'chunk_index'.
        """
        try:
            query_embedding = self.embedding_client.get_embedding(query)
            results = self.documentation_collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                include=['documents', 'metadatas', 'distances']
            )

            relevant_docs = []
            if results and results["distances"] and results["documents"]:
                for i in range(len(results["distances"][0])):
                    distance = results["distances"][0][i]
                    if distance >= min_distance:
                        relevant_docs.append({
                            "document": results["documents"][0][i],
                            "source": results["metadatas"][0][i].get("source"),
                            "chunk_index": results["metadatas"][0][i].get("chunk_index"),
                            "distance": distance
                        })
            self.logger.info(f"  Found {len(relevant_docs)} relevant documentation chunks for query.")
            return relevant_docs
        except Exception as e:
            self.logger.error(f"  Failed to query documentation: {e}")
            return []
    def query_documentation_by_source(
        self, query: str, n_results: int = 3, source_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Enhanced query with optional source filter.
        source_filter: Filter results by file source (e.g., 'requirements.md')
        """
        all_results = self.query_documentation(query, n_results * 2)  # Get more to filter
        
        if source_filter:
            filtered = [r for r in all_results if source_filter in r.get("source", "")]
            return filtered[:n_results]
        
        return all_results[:n_results]

    def get_knowledge_workspace_status(self) -> Dict[str, Any]:
        """Returns status of the Knowledge Workspace."""
        status = {
            "knowledge_workspace_path": str(self.knowledge_workspace),
            "references": {
                "path": str(self.references_dir),
                "exists": self.references_dir.exists(),
                "files": []
            },
            "indexed": {
                "path": str(self.indexed_cache),
                "total_vectors": len(self.documentation_collection.get()["ids"]),
            },
            "summaries": {
                "path": str(self.summaries_dir),
                "count": len(list(self.summaries_dir.glob("*.json"))) if self.summaries_dir.exists() else 0,
            }
        }

        # List files in references
        if self.references_dir.exists():
            for file_path in self.references_dir.rglob("*"):
                if file_path.is_file():
                    metadata = self.ingester.get_file_metadata(file_path)
                    status["references"]["files"].append({
                        "name": file_path.name,
                        "format": file_path.suffix.lower(),
                        **metadata
                    })

        return status

    def upload_to_workspace(self, source_file: Path) -> bool:
        """
        Uploads a reference document to the Knowledge Workspace.
        Copies file to references/ directory.
        """
        if not source_file.exists():
            self.logger.error(f"Source file not found: {source_file}")
            return False

        try:
            dest_file = self.references_dir / source_file.name
            import shutil
            shutil.copy2(source_file, dest_file)
            self.logger.info(f"✓ Uploaded {source_file.name} to Knowledge Workspace")
            return True
        except Exception as e:
            self.logger.error(f"Failed to upload file: {e}")
            return False

    def clear_collection(self):
        """Clears all indexed documentation from ChromaDB."""
        try:
            self.chroma_client.delete_collection(name="documentation_store")
            self.documentation_collection = self.chroma_client.get_or_create_collection(
                name="documentation_store"
            )
            self.logger.info("✓ Cleared documentation collection")
            return True
        except Exception as e:
            self.logger.error(f"Failed to clear collection: {e}")
            return False
