# src/utils/core/scanners/rag_context_selector.py

import chromadb
from chromadb.utils import embedding_functions
import logging
from pathlib import Path
from typing import Dict, List, Any

from src.utils.core.chroma_manager import ChromaClientManager

logger = logging.getLogger(__name__)

class RAGContextSelector:
    def __init__(self, settings_manager: dict, project_root: Path, docs_retriever):
        """
        Initializes the RAGContextSelector.

        Args:
            settings_manager: The settings manager.
            project_root (Path): The root directory of the project.
            docs_retriever: The document retriever.
        """
        self.settings = settings_manager
        self.project_root = project_root
        self.docs_retriever = docs_retriever
        self.client = ChromaClientManager.get_client(settings_manager, project_root)

        self.knowledge_collection_name = self.settings.get('knowledge_workspace', {}).get('collection_name', 'knowledge_base')
        self.error_collection_name = self.settings.get('error_knowledge_base', {}).get('collection_name', 'error_knowledge_base')

        self.embedding_function = embedding_functions.DefaultEmbeddingFunction()
        
        try:
            self.knowledge_collection = self.client.get_or_create_collection(
                name=self.knowledge_collection_name,
                embedding_function=self.embedding_function
            )
            self.error_collection = self.client.get_or_create_collection(
                name=self.error_collection_name,
                embedding_function=self.embedding_function
            )
            logger.info(f"Successfully connected to collections: '{self.knowledge_collection_name}' and '{self.error_collection_name}'.")

        except Exception as e:
            logger.error(f"Error connecting to ChromaDB collections: {e}")
            self.knowledge_collection = None
            self.error_collection = None

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

