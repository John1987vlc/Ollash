import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import chromadb

from src.utils.core.ollama_client import OllamaClient
from src.utils.core.agent_logger import AgentLogger


class DocumentationManager:
    def __init__(self, project_root: Path, logger: AgentLogger, config: Optional[Dict] = None):
        self.project_root = project_root
        self.logger = logger
        self.config = config or {}

        self.chroma_client = chromadb.Client()
        self.documentation_collection = self.chroma_client.get_or_create_collection(name="documentation_store")

        # Embedding client - reuse or create new
        models_config = self.config.get("models", {})
        ollama_url = os.environ.get(
            "OLLASH_OLLAMA_URL",
            self.config.get("ollama_url", "http://localhost:11434"),
        )
        self.embedding_client = OllamaClient(
            url=ollama_url,
            model=models_config.get("embedding",
                   self.config.get("ollama_embedding_model", "all-minilm")),
            timeout=self.config.get("timeout", 300),
            logger=self.logger,
            config=self.config
        )
        self.logger.info("DocumentationManager initialized.")

    def index_documentation(self, doc_path: Path, chunk_size: int = 1000, overlap: int = 200):
        """
        Indexes documentation from a given path (file or directory) into ChromaDB.
        Splits content into chunks, generates embeddings, and stores them.
        """
        if doc_path.is_file():
            self._index_file(doc_path, chunk_size, overlap)
        elif doc_path.is_dir():
            for file_path in doc_path.rglob("*"):
                if file_path.is_file():
                    self._index_file(file_path, chunk_size, overlap)
        self.logger.info(f"Indexing complete for {doc_path}.")

    def _index_file(self, file_path: Path, chunk_size: int, overlap: int):
        """Indexes a single documentation file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            chunks = self._chunk_text(content, chunk_size, overlap)
            
            embeddings = []
            metadatas = []
            ids = []

            for i, chunk in enumerate(chunks):
                embedding = self.embedding_client.get_embedding(chunk)
                embeddings.append(embedding)
                metadatas.append({"source": str(file_path.relative_to(self.project_root)), "chunk_index": i})
                ids.append(f"{file_path.name}-{i}")
            
            if embeddings:
                self.documentation_collection.add(
                    embeddings=embeddings,
                    documents=chunks,
                    metadatas=metadatas,
                    ids=ids
                )
                self.logger.info(f"  Indexed {len(chunks)} chunks from {file_path.name}")
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
