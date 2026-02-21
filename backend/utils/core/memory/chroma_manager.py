# src/utils/core/chroma_manager.py

import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class ChromaClientManager:
    _client_instance = None
    _initialized_settings = None

    @classmethod
    def get_client(cls, settings_manager: dict, project_root: Path):
        if cls._client_instance is None:
            # Evaluate settings only once
            is_persistent = settings_manager.get("chroma_db", {}).get("is_persistent", False)

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
                settings = Settings(anonymized_telemetry=False)

            try:
                cls._client_instance = chromadb.Client(settings)
                cls._initialized_settings = settings
                logger.info("ChromaDB client initialized successfully.")
            except Exception as e:
                # If it fails because an instance already exists, try to get the existing one
                if "already exists" in str(e):
                    logger.warning("ChromaDB instance already exists, attempting to return default client.")
                    cls._client_instance = chromadb.Client()
                else:
                    logger.error(f"Failed to initialize ChromaDB client: {e}")
                    raise

        return cls._client_instance
