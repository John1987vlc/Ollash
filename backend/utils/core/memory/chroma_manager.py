# src/utils/core/chroma_manager.py
# chromadb is imported lazily inside get_client() to avoid loading ~800 heavy
# transitive modules (numpy, grpc, opentelemetry, docker) at import time.

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ChromaClientManager:
    _client_instance = None
    _initialized_settings = None

    @classmethod
    def get_client(cls, settings_manager: dict, project_root: Path):
        if cls._client_instance is None:
            import chromadb  # noqa: PLC0415 — intentional lazy import
            from chromadb.config import Settings  # noqa: PLC0415

            # Evaluate settings only once
            is_persistent = settings_manager.get("chroma_db", {}).get("is_persistent", False)
            db_path = str(project_root / ".ollash" / "chroma_db")

            try:
                if is_persistent:
                    logger.info(f"ChromaDB client is persistent, path: {db_path}")
                    try:
                        # Modern ChromaDB 0.4+ approach
                        cls._client_instance = chromadb.PersistentClient(path=db_path)
                        logger.info("ChromaDB PersistentClient initialized successfully.")
                    except Exception as e:
                        logger.warning(f"Failed to initialize PersistentClient, falling back to legacy Settings: {e}")
                        settings = Settings(
                            chroma_db_impl="duckdb+parquet",
                            persist_directory=db_path,
                            anonymized_telemetry=False,
                        )
                        cls._client_instance = chromadb.Client(settings)
                        cls._initialized_settings = settings
                else:
                    logger.info("ChromaDB client is ephemeral (in-memory).")
                    # EphemeralClient is the recommended way for in-memory in modern chroma
                    cls._client_instance = chromadb.EphemeralClient()
            except Exception as e:
                # If it fails because an instance already exists, try to get the existing one
                if "already exists" in str(e):
                    logger.warning("ChromaDB instance already exists, attempting to return default client.")
                    cls._client_instance = chromadb.Client()
                else:
                    logger.error(f"Failed to initialize ChromaDB client: {e}")
                    raise

        return cls._client_instance
