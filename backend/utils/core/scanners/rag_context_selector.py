# src/utils/core/scanners/rag_context_selector.py

from chromadb.utils import embedding_functions
import logging
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass

from backend.utils.core.chroma_manager import ChromaClientManager

logger = logging.getLogger(__name__)

@dataclass
class CodeFragment:
    """Represents a code fragment with metadata."""
    file_path: str
    language: str
    content: str
    start_line: int = 1
    end_line: int = 1

class RAGContextSelector:
    def __init__(self, settings_manager: dict = None, project_root: Path = None, docs_retriever=None, logger=None):
        """
        Initializes the RAGContextSelector.

        Args:
            settings_manager: The settings manager.
            project_root (Path): The root directory of the project.
            docs_retriever: The document retriever.
            logger: Logger instance.
        """
        self.logger = logger or logging.getLogger(__name__)
        self.settings = settings_manager or {}
        self.project_root = project_root
        self.docs_retriever = docs_retriever
        self.max_context_tokens = 4000

        try:
            self.client = ChromaClientManager.get_client(settings_manager or {}, project_root or Path.cwd())
        except Exception as e:
            self.logger.warning(f"Could not initialize ChromaDB client: {e}")
            self.client = None

        self.knowledge_collection_name = self.settings.get('knowledge_workspace', {}).get('collection_name', 'knowledge_base')
        self.error_collection_name = self.settings.get('error_knowledge_base', {}).get('collection_name', 'error_knowledge_base')

        self.embedding_function = embedding_functions.DefaultEmbeddingFunction()

        self.knowledge_collection = None
        self.error_collection = None

        if self.client:
            try:
                self.knowledge_collection = self.client.get_or_create_collection(
                    name=self.knowledge_collection_name,
                    embedding_function=self.embedding_function
                )
                self.error_collection = self.client.get_or_create_collection(
                    name=self.error_collection_name,
                    embedding_function=self.embedding_function
                )
                self.logger.info(f"Successfully connected to collections: '{self.knowledge_collection_name}' and '{self.error_collection_name}'.")

            except Exception as e:
                self.logger.error(f"Error connecting to ChromaDB collections: {e}")
                self.knowledge_collection = None
                self.error_collection = None

    def index_code_fragments(self, files: Dict[str, str]) -> None:
        """Index code fragments for semantic search."""
        if not self.knowledge_collection:
            self.logger.warning("Knowledge collection not available for indexing.")
            return

        try:
            for file_path, content in files.items():
                self.knowledge_collection.add(
                    documents=[content],
                    metadatas=[{"source": file_path}],
                    ids=[file_path]
                )
            self.logger.info(f"Indexed {len(files)} files.")
        except Exception as e:
            self.logger.error(f"Error indexing fragments: {e}")

    def select_relevant_fragments(self, query: str, max_fragments: int = 5) -> List[CodeFragment]:
        """Select relevant code fragments based on query."""
        if not self.knowledge_collection:
            return []

        try:
            results = self.knowledge_collection.query(
                query_texts=[query],
                n_results=max_fragments,
                include=["documents", "metadatas"]
            )

            fragments = []
            if results and results.get("documents"):
                for docs, metadatas in zip(results["documents"], results["metadatas"]):
                    for doc, metadata in zip(docs, metadatas):
                        fragment = CodeFragment(
                            file_path=metadata.get("source", "unknown"),
                            language="python",
                            content=doc,
                            start_line=1,
                            end_line=len(doc.split('\n'))
                        )
                        fragments.append(fragment)

            return fragments
        except Exception as e:
            self.logger.error(f"Error selecting fragments: {e}")
            return []

    def build_context(self, task_description: str, required_files: List[str] = None) -> Tuple[str, int]:
        """Build context for a task respecting token limits."""
        context_parts = []
        token_count = 0

        # Select relevant fragments
        fragments = self.select_relevant_fragments(task_description)

        for fragment in fragments:
            # Rough token estimation (1 token ≈ 4 chars)
            fragment_tokens = len(fragment.content) // 4

            if token_count + fragment_tokens <= self.max_context_tokens:
                context_parts.append(f"# {fragment.file_path}\n{fragment.content}")
                token_count += fragment_tokens
            else:
                break

        context = "\n---\n".join(context_parts)
        return context, token_count

    def query_knowledge_base(self, query_texts, n_results=5):
        """
        Queries the knowledge base for relevant context.
        """
        if not self.knowledge_collection:
            logger.warning("Knowledge collection is not available.")
            return []
        try:
            results = self.knowledge_collection.query(
                query_texts=query_texts,
                n_results=n_results
            )
            return results
        except Exception as e:
            logger.error(f"Error querying knowledge base: {e}")
            return []

    def query_error_knowledge_base(self, error_message, n_results=3):
        """
        Queries the error knowledge base for solutions to similar past errors.
        """
        if not self.error_collection:
            logger.warning("Error collection is not available.")
            return []
        try:
            results = self.error_collection.query(
                query_texts=[error_message],
                n_results=n_results
            )
            return results['documents']
        except Exception as e:
            logger.error(f"Error querying error knowledge base: {e}")
            return []

    def get_context(self, prompt, error_context=None):
        """
        Retrieves relevant context from the knowledge base and error database.
        """
        context = []

        if self.docs_retriever:
            retrieved_docs = self.docs_retriever.get_relevant_documents(prompt)
            if retrieved_docs:
                context.extend([doc.page_content for doc in retrieved_docs])
                logger.debug(f"Retrieved {len(retrieved_docs)} documents from DocsManager.")

        knowledge_context_results = self.query_knowledge_base(query_texts=[prompt])
        if knowledge_context_results and knowledge_context_results['documents']:
            context.extend(knowledge_context_results['documents'][0])
            logger.debug(f"Retrieved {len(knowledge_context_results['documents'][0])} documents from Knowledge Base.")

        if error_context:
            error_solutions = self.query_error_knowledge_base(error_message=error_context)
            if error_solutions:
                context.extend(error_solutions[0])
                logger.debug(f"Retrieved {len(error_solutions[0])} solutions from Error KB.")

        return "\n---\n".join(context)

    def select_relevant_files(self, query: str, available_files: Dict[str, str], max_files: int = 5) -> Dict[str, str]:
        """Selects contextually relevant files using semantic search."""
        if not self.knowledge_collection:
            logger.warning("Knowledge collection not available for file selection.")
            return {}

        query_texts = [query] + list(available_files.keys())

        try:
            results = self.knowledge_collection.query(
                query_texts=query_texts,
                n_results=max_files,
                include=["metadatas"]
            )

            if not results or not results.get("metadatas"):
                return {}

            relevant_paths = set()
            for metadata_list in results["metadatas"]:
                for metadata in metadata_list:
                    if "source" in metadata:
                        relevant_paths.add(metadata["source"])

            # Return the content of the relevant files
            context_files = {
                path: available_files[path]
                for path in relevant_paths
                if path in available_files
            }

            return dict(list(context_files.items())[:max_files])

        except Exception as e:
            logger.error(f"Error during RAG file selection: {e}")
            return {}


class SemanticContextManager:
    """High-level API for managing semantic context across phases."""

    def __init__(self, logger=None, project_root: Path = None, settings_manager: dict = None):
        """Initialize the semantic context manager."""
        self.logger = logger or logging.getLogger(__name__)
        self.project_root = project_root or Path.cwd()
        self.settings = settings_manager or {}
        self.selector = RAGContextSelector(
            settings_manager=self.settings,
            project_root=self.project_root,
            logger=self.logger
        )

    def prepare_context_for_phase(self, phase: str, files: Dict[str, str], task: str) -> str:
        """Prepare context for a specific phase."""
        try:
            # Index the files
            self.selector.index_code_fragments(files)

            # Build context based on the task
            context, _ = self.selector.build_context(task_description=task)

            self.logger.info(f"Prepared context for phase '{phase}'")
            return context
        except Exception as e:
            self.logger.error(f"Error preparing context for phase '{phase}': {e}")
            return ""
