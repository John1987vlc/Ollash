# src/utils/core/chroma_manager.py

import chromadb
from chromadb.config import Settings
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class ChromaClientManager:
    _client_instance = None

    @classmethod
    def get_client(cls, settings_manager: dict, project_root: Path):
        if cls._client_instance is None:
            is_persistent = settings_manager.get('chroma_db', {}).get('is_persistent', False)
            
            if is_persistent:
                db_path = str(project_root / ".ollash" / "chroma_db")
                logger.info(f"ChromaDB client is persistent, path: {db_path}")
                settings = Settings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory=db_path,
                    anonymized_telemetry=False,
                )
            else:
                logger.info("ChromaDB client is ephemeral.")
                # Settings for an ephemeral client.
                # Note: ChromaDB's default is an ephemeral in-memory client.
                settings = Settings(anonymized_telemetry=False)

            try:
                cls._client_instance = chromadb.Client(settings)
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB client: {e}")
                raise

        return cls._client_instance
