"""
Fragment Cache System for Auto-Generated Projects

Caches reusable code fragments (headers, boilerplate, standard structures)
to avoid redundant LLM calls and improve generation speed.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from backend.utils.core.agent_logger import AgentLogger


class FragmentCache:
    """
    Caches common code fragments to reduce LLM calls.

    Fragments are indexed by:
    - Fragment type (license_header, class_boilerplate, function_template, etc.)
    - Language (python, javascript, go, rust, etc.)
    - Context hash (md5 of project context)
    """

    FRAGMENT_TYPES = {
        "license_header": "License headers (Apache, MIT, GPL, etc.)",
        "test_boilerplate": "Test file structure and imports",
        "class_template": "Standard class definition template",
        "async_pattern": "Async/await pattern implementations",
        "error_handling": "Exception handling patterns",
        "logging_setup": "Logging initialization patterns",
        "dependency_declaration": "Package/library declarations",
        "config_template": "Configuration file templates",
    }

    def __init__(
        self, cache_dir: Path, logger: AgentLogger, enable_persistence: bool = True
    ):
        """
        Initialize the fragment cache.

        Args:
            cache_dir: Directory to store cache files
            logger: Logger instance
            enable_persistence: If True, persist cache to disk
        """
        self.cache_dir = Path(cache_dir)
        self.logger = logger
        self.enable_persistence = enable_persistence

        # In-memory cache
        self._memory_cache: Dict[str, Dict] = {}

        # Cache metadata
        self.cache_file = self.cache_dir / ".fragment_cache.json"

        if self.enable_persistence:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    def _generate_cache_key(
        self, fragment_type: str, language: str, context_hash: str = ""
    ) -> str:
        """Generate a unique cache key for a fragment."""
        context_part = f":{context_hash}" if context_hash else ""
        return f"{fragment_type}:{language}{context_part}".lower()

    def _compute_context_hash(self, context: str) -> str:
        """Compute MD5 hash of context for cache keying."""
        return hashlib.md5(context.encode()).hexdigest()[:8]

    def get(
        self, fragment_type: str, language: str, context: str = "", validate_fn=None
    ) -> Optional[str]:
        """
        Retrieve a cached fragment.

        Args:
            fragment_type: Type of fragment (e.g., 'license_header')
            language: Programming language
            context: Optional context string for more specific matches
            validate_fn: Optional validation function to check if fragment is still valid

        Returns:
            Cached fragment string, or None if not found or invalid
        """
        context_hash = self._compute_context_hash(context) if context else ""
        cache_key = self._generate_cache_key(fragment_type, language, context_hash)

        # Check memory cache first
        if cache_key in self._memory_cache:
            fragment_data = self._memory_cache[cache_key]

            # Validate fragment if validator provided
            if validate_fn:
                if not validate_fn(fragment_data.get("content", "")):
                    self.logger.debug(f"Fragment validation failed for {cache_key}")
                    return None

            self.logger.debug(f"Fragment cache HIT for {cache_key}")
            fragment_data["hits"] = fragment_data.get("hits", 0) + 1
            return fragment_data.get("content")

        self.logger.debug(f"Fragment cache MISS for {cache_key}")
        return None

    def set(
        self,
        fragment_type: str,
        language: str,
        content: str,
        context: str = "",
        metadata: Dict = None,
    ) -> None:
        """
        Store a fragment in the cache.

        Args:
            fragment_type: Type of fragment
            language: Programming language
            content: Fragment content
            context: Optional context string
            metadata: Optional metadata dict (description, source, etc.)
        """
        if not content:
            return

        context_hash = self._compute_context_hash(context) if context else ""
        cache_key = self._generate_cache_key(fragment_type, language, context_hash)

        self._memory_cache[cache_key] = {
            "content": content,
            "created_at": datetime.now().isoformat(),
            "hits": 0,
            "fragment_type": fragment_type,
            "language": language,
            "metadata": metadata or {},
        }

        self.logger.debug(f"Fragment cached: {cache_key}")

        if self.enable_persistence:
            self._save_to_disk()

    def get_by_pattern(self, fragment_type: str, language: str) -> List[str]:
        """
        Get all cached fragments matching a pattern (ignoring context).
        Useful for finding variants of a fragment type.
        """
        prefix = self._generate_cache_key(fragment_type, language, "").rstrip(":")
        matches = []

        for key, data in self._memory_cache.items():
            if key.startswith(prefix):
                matches.append(data.get("content", ""))

        return matches

    def clear(self) -> None:
        """Clear all cached fragments."""
        self._memory_cache.clear()
        if self.enable_persistence and self.cache_file.exists():
            self.cache_file.unlink()
        self.logger.info("Fragment cache cleared")

    def stats(self) -> Dict:
        """Return cache statistics."""
        if not self._memory_cache:
            return {"status": "empty", "fragments": 0}

        total_fragments = len(self._memory_cache)
        total_hits = sum(f.get("hits", 0) for f in self._memory_cache.values())
        fragment_types = set(
            f.get("fragment_type") for f in self._memory_cache.values()
        )
        languages = set(f.get("language") for f in self._memory_cache.values())

        return {
            "total_fragments": total_fragments,
            "total_hits": total_hits,
            "fragment_types": len(fragment_types),
            "languages": len(languages),
            "avg_hits_per_fragment": total_hits / total_fragments
            if total_fragments > 0
            else 0,
        }

    def _save_to_disk(self) -> None:
        """Persist cache to disk."""
        if not self.enable_persistence:
            return

        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self._memory_cache, f, indent=2, default=str)
        except Exception as e:
            self.logger.warning(f"Failed to persist fragment cache: {e}")

    def _load_from_disk(self) -> None:
        """Load cache from disk."""
        if not self.cache_file.exists():
            return

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                self._memory_cache = json.load(f)
            self.logger.info(
                f"Loaded {len(self._memory_cache)} fragments from disk cache"
            )
        except Exception as e:
            self.logger.warning(f"Failed to load fragment cache from disk: {e}")
            self._memory_cache = {}

    def preload_common_fragments(self, language: str) -> None:
        """
        Preload common fragments for a language.
        Should be called during initialization for frequently used languages.
        """
        common_fragments = self._get_common_fragments_for_language(language)

        for fragment_type, content, metadata in common_fragments:
            if self.get(fragment_type, language) is None:
                self.set(fragment_type, language, content, metadata=metadata)

        self.logger.info(f"Preloaded common fragments for {language}")

    @staticmethod
    def _get_common_fragments_for_language(language: str) -> List[tuple]:
        """Return a list of (fragment_type, content, metadata) for common language patterns."""

        fragments = {
            "python": [
                (
                    "license_header",
                    '"""\\nMIT License\\n\\nCopyright (c) 2026\\n\\nPermission is hereby granted...\\n"""\\n',
                    {"license": "MIT", "language": "python"},
                ),
                (
                    "test_boilerplate",
                    '''import pytest\\nfrom unittest.mock import Mock, patch\\n\\n\\nclass Test{{ClassName}}:\\n    """Test suite for {{module_name}}."""\\n\\n    def setup_method(self):\\n        """Set up test fixtures."""\\n        pass\\n\\n    def teardown_method(self):\\n        """Clean up after tests."""\\n        pass\\n''',
                    {"test_framework": "pytest"},
                ),
            ],
            "javascript": [
                (
                    "license_header",
                    "/**\\n * MIT License\\n * Copyright (c) 2026\\n */\\n",
                    {"license": "MIT", "language": "javascript"},
                ),
                (
                    "test_boilerplate",
                    """const assert = require('assert');\\n\\ndescribe('{{ClassName}}', () => {\\n  before(() => {\\n    // Setup\\n  });\\n\\n  it('should...', () => {\\n    assert.ok(true);\\n  });\\n});""",
                    {"test_framework": "mocha"},
                ),
            ],
            "go": [
                (
                    "test_boilerplate",
                    """package {{package}}\\n\\nimport "testing"\\n\\nfunc Test{{FunctionName}}(t *testing.T) {\\n  // Test logic\\n}\\n""",
                    {"test_framework": "testing"},
                ),
            ],
        }

        return fragments.get(language, [])
