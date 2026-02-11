import subprocess
import json
import time
import requests
import asyncio
import aiohttp
from pathlib import Path
from typing import Dict, List, Optional
from collections import deque
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.utils.core.agent_logger import AgentLogger
from src.utils.core.gpu_aware_rate_limiter import GPUAwareRateLimiter
from src.utils.core.embedding_cache import EmbeddingCache
from src.utils.core.model_health_monitor import ModelHealthMonitor


class RateLimiter:
    """Simple token-bucket rate limiter for API requests."""

    def __init__(self, requests_per_minute: int = 60, tokens_per_minute: int = 100000):
        self.rpm = requests_per_minute
        self.tpm = tokens_per_minute
        self._request_timestamps: deque = deque()
        self._token_usage: deque = deque()  # (timestamp, tokens)

    def wait_if_needed(self):
        """Blocks until a request is allowed under the rate limit."""
        now = time.monotonic()
        # Purge old timestamps (older than 60s)
        while self._request_timestamps and now - self._request_timestamps[0] > 60:
            self._request_timestamps.popleft()
        if len(self._request_timestamps) >= self.rpm:
            sleep_time = 60 - (now - self._request_timestamps[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
        self._request_timestamps.append(time.monotonic())

    def record_tokens(self, token_count: int):
        """Records token usage for rate tracking."""
        now = time.monotonic()
        while self._token_usage and now - self._token_usage[0][0] > 60:
            self._token_usage.popleft()
        self._token_usage.append((now, token_count))


class OllamaClient:
    def __init__(self, url: str, model: str, timeout: int, logger: AgentLogger, config: Dict, model_health_monitor: Optional[ModelHealthMonitor] = None):
        self.base_url = url.rstrip('/')
        self.chat_url = f"{self.base_url}/api/chat"
        self.embed_url = f"{self.base_url}/api/embed"
        self.model = model
        self.logger = logger
        self.config = config
        self.model_health_monitor = model_health_monitor

        # Configure retry strategy for sync requests
        max_retries = min(self.config.get("ollama_max_retries", 5), 10)
        backoff_factor = min(self.config.get("ollama_backoff_factor", 1.0), 5.0)
        status_forcelist = self.config.get("ollama_retry_status_forcelist", [429, 500, 502, 503, 504])

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            allowed_methods=["POST"],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.http_session = requests.Session()
        self.http_session.mount("http://", adapter)
        self.http_session.mount("https://", adapter)

        # Aiohttp session for async requests
        self.aiohttp_session = aiohttp.ClientSession()

        # Timeout for individual requests
        self.timeout = timeout

        # GPU-aware rate limiting (replaces simple RateLimiter)
        rate_config = self.config.get("rate_limiting", {})
        gpu_config = self.config.get("gpu_rate_limiter", {})
        self._rate_limiter = GPUAwareRateLimiter(
            base_rpm=rate_config.get("requests_per_minute", 60),
            tokens_per_minute=rate_config.get("max_tokens_per_minute", 100000),
            degradation_threshold_ms=gpu_config.get("degradation_threshold_ms", 5000.0),
            recovery_threshold_ms=gpu_config.get("recovery_threshold_ms", 2000.0),
            min_rpm=gpu_config.get("min_rpm", 5),
            ema_alpha=gpu_config.get("ema_alpha", 0.3),
            logger=logger,
        )

        # Embedding model configuration
        models_config = self.config.get("models", {})
        self.embedding_model = models_config.get("embedding",
                                self.config.get("ollama_embedding_model", "all-minilm"))

        # Embedding cache
        cache_config = self.config.get("embedding_cache", {})
        cache_persist_path = None
        if cache_config.get("persist_to_disk", True):
            cache_persist_path = Path(self.config.get("project_root", ".")) / ".embedding_cache.json"
        self._embedding_cache = EmbeddingCache(
            max_size=cache_config.get("max_size", 10000),
            ttl_seconds=cache_config.get("ttl_seconds", 3600),
            persist_path=cache_persist_path,
            logger=logger,
        )

    async def close(self):
        """Closes the aiohttp session."""
        await self.aiohttp_session.close()

    async def _apull_model(self, model_name: str) -> bool:
        """Asynchronously pulls a specified Ollama model."""
        self.logger.info(f"Attempting to pull Ollama model: {model_name}...")
        command = ["ollama", "pull", model_name]
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)

            if process.returncode == 0:
                self.logger.info(f"Successfully pulled model {model_name}:\n{stdout.decode()}")
                return True
            else:
                self.logger.error(f"Failed to pull model {model_name}. Error:\n{stderr.decode()}")
                return False
        except asyncio.TimeoutError:
            self.logger.error(f"Ollama pull command for {model_name} timed out after 300 seconds.")
            return False
        except FileNotFoundError:
            self.logger.error("'ollama' command not found. Please ensure Ollama is installed and in your system's PATH.")
            return False
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while pulling model {model_name}: {e}")
            return False

    def _pull_model(self, model_name: str) -> bool:
        """
        Attempts to pull a specified Ollama model.
        Returns True if successful, False otherwise.
        """
        self.logger.info(f"Attempting to pull Ollama model: {model_name}...")
        command = ["ollama", "pull", model_name]
        try:
            process = subprocess.run(command, check=True, capture_output=True, text=True, timeout=300)
            self.logger.info(f"Successfully pulled model {model_name}:\n{process.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to pull model {model_name}. Error:\n{e.stderr}")
            return False
        except subprocess.TimeoutExpired:
            self.logger.error(f"Ollama pull command for {model_name} timed out after 300 seconds.")
            return False
        except FileNotFoundError:
            self.logger.error("'ollama' command not found. Please ensure Ollama is installed and in your system's PATH.")
            return False
        except Exception as e:
            self.logger.error(f"An unexpected error occurred while pulling model {model_name}: {e}")
            return False

    async def achat(self, messages: List[Dict], tools: List[Dict], options_override: Dict | None = None) -> tuple[Dict, Dict]:
        default_options = {
            "temperature": 0.1,
            "num_predict": 4096,
            "keep_alive": "0s"
        }
        if options_override:
            default_options.update(options_override)

        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "options": default_options
        }
        
        start_time = time.monotonic()
        success = False
        try:
            await self._rate_limiter.a_wait_if_needed()

            self.logger.debug(f"Sending async request to {self.chat_url}")
            tool_names = [t["function"]["name"] for t in tools]
            self.logger.debug(f"Available tools: {', '.join(tool_names)}")
            
            _request_start = time.monotonic()
            async with self.aiohttp_session.post(self.chat_url, json=payload, timeout=self.timeout) as response:
                _elapsed_ms = (time.monotonic() - _request_start) * 1000
                self._rate_limiter.record_response_time(_elapsed_ms)
                self.logger.debug(f"Async response status: {response.status} ({_elapsed_ms:.0f}ms)")
                response.raise_for_status()
                data = await response.json()

            prompt_chars = sum(len(json.dumps(m)) for m in messages)
            completion_chars = len(json.dumps(data.get("message", {})))
            usage = {
                "prompt_tokens": prompt_chars // 4,
                "completion_tokens": completion_chars // 4,
                "total_tokens": (prompt_chars + completion_chars) // 4
            }
            success = True
            return data, usage

        except aiohttp.ClientResponseError as e:
            self.logger.error(f"Ollama API Error (Status {e.status}): {e.message}")
            if e.status == 404 and "model not found" in e.message.lower():
                if await self._apull_model(self.model):
                    return await self.achat(messages, tools, options_override)
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in async API call: {str(e)}", e)
            raise
        finally:
            if self.model_health_monitor:
                latency = time.monotonic() - start_time
                self.model_health_monitor.record_request(self.model, latency, success)

    def chat(self, messages: List[Dict], tools: List[Dict], options_override: Dict | None = None) -> tuple[Dict, Dict]:
        """
        Returns (response_data, usage_stats)
        Enhanced with better error handling and logging, and retry mechanism.

        options_override: if provided, merged on top of default options.
                          Use this to control num_ctx, num_predict, temperature, etc.
        """
        default_options = {
            "temperature": 0.1,
            "num_predict": 4096,
            "keep_alive": "0s"
        }
        if options_override:
            default_options.update(options_override)

        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "options": default_options
        }
        
        start_time = time.monotonic()
        success = False
        try:
            # Rate limiting
            self._rate_limiter.wait_if_needed()

            # Log request details
            self.logger.debug(f"Sending request to {self.chat_url}")
            self.logger.debug(f"Model: {self.model}")
            self.logger.debug(f"Messages count: {len(messages)}")
            self.logger.debug(f"Tools count: {len(tools)}")
            
            # Log tool names for debugging
            tool_names = [t["function"]["name"] for t in tools]
            self.logger.debug(f"Available tools: {', '.join(tool_names)}")
            
            # Make request using session with retry logic (timed for GPU-aware rate limiter)
            _request_start = time.monotonic()
            r = self.http_session.post(self.chat_url, json=payload, timeout=self.timeout)
            _elapsed_ms = (time.monotonic() - _request_start) * 1000
            self._rate_limiter.record_response_time(_elapsed_ms)

            # Log response status
            self.logger.debug(f"Response status: {r.status_code} ({_elapsed_ms:.0f}ms)")

            # Check for errors
            r.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            data = r.json()
            
            # Estimate tokens (rough approximation: 1 token ≈ 4 chars)
            prompt_chars = sum(len(json.dumps(m)) for m in messages)
            completion_chars = len(json.dumps(data.get("message", {})))
            
            usage = {
                "prompt_tokens": prompt_chars // 4,
                "completion_tokens": completion_chars // 4,
                "total_tokens": (prompt_chars + completion_chars) // 4
            }
            success = True
            return data, usage
            
        except requests.exceptions.Timeout:
            self.logger.error(f"Request timeout after {self.timeout}s")
            raise
        except requests.exceptions.ConnectionError:
            self.logger.error(f"Connection error: Cannot connect to Ollama at {self.chat_url}")
            self.logger.error("Make sure Ollama is running: 'ollama serve'")
            raise
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"Ollama API Error (Status {r.status_code}): {e.response.text[:500]}")
            
            # Check for "model not found" (HTTP 404) and attempt to pull
            if r.status_code == 404 and "model not found" in e.response.text.lower():
                self.logger.warning(f"Model '{self.model}' not found. Attempting to pull...")
                if self._pull_model(self.model):
                    self.logger.info(f"Model '{self.model}' pulled successfully. Retrying chat request...")
                    # After successful pull, retry the chat request once.
                    try:
                        r = self.http_session.post(self.chat_url, json=payload, timeout=self.timeout)
                        r.raise_for_status()
                        data = r.json()
                        prompt_chars = sum(len(json.dumps(m)) for m in messages)
                        completion_chars = len(json.dumps(data.get("message", {})))
                        usage = {
                            "prompt_tokens": prompt_chars // 4,
                            "completion_tokens": completion_chars // 4,
                            "total_tokens": (prompt_chars + completion_chars) // 4
                        }
                        success = True
                        return data, usage
                    except Exception as retry_e:
                        self.logger.error(f"Retry after model pull failed for '{self.model}': {retry_e}")
                        raise # Re-raise if retry fails
                else:
                    self.logger.error(f"Failed to pull model '{self.model}'. Cannot complete request.")
                    raise # Re-raise original error if pull fails
            
            # Original tool not found check (only if model pull logic didn't handle it)
            if "tool" in e.response.text.lower() and "not found" in e.response.text.lower():
                self.logger.warning("The model tried to use a tool that doesn't exist.")
                # Log available tools for debugging (tool_names was defined earlier in chat method)
                self.logger.warning(f"Available tools: {', '.join(tool_names)}") # tool_names is already defined above
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in API call: {str(e)}", e)
            raise
        finally:
            if self.model_health_monitor:
                latency = time.monotonic() - start_time
                self.model_health_monitor.record_request(self.model, latency, success)

    async def aget_embedding(self, text: str) -> List[float]:
        cached = self._embedding_cache.get(text)
        if cached is not None:
            self.logger.debug("Embedding cache hit")
            return cached

        payload = {
            "model": self.embedding_model,
            "prompt": text,
            "options": {"num_predict": 1, "keep_alive": "0s"}
        }
        try:
            self.logger.debug(f"Sending async embedding request to {self.embed_url}")
            async with self.aiohttp_session.post(self.embed_url, json=payload, timeout=self.timeout) as response:
                response.raise_for_status()
                data = await response.json()
                embeddings = data.get("embedding")
                if not embeddings:
                    raise ValueError("No embedding found in Ollama API response.")
                self._embedding_cache.put(text, embeddings)
                return embeddings
        except aiohttp.ClientResponseError as e:
            if e.status == 404 and "model not found" in e.message.lower():
                if await self._apull_model(self.embedding_model):
                    return await self.aget_embedding(text)
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in async embedding API call: {str(e)}", e)
            raise

    def get_embedding(self, text: str) -> List[float]:
        """
        Generates embeddings for a given text using Ollama's /api/embed endpoint.
        Uses local cache to avoid redundant API calls for identical text.
        """
        # Check cache first
        cached = self._embedding_cache.get(text)
        if cached is not None:
            self.logger.debug("Embedding cache hit")
            return cached

        payload = {
            "model": self.embedding_model,
            "prompt": text,
            "options": {
                "num_predict": 1, # Only need embedding, not text prediction
                "keep_alive": "0s"
            }
        }
        try:
            self.logger.debug(f"Sending embedding request to {self.embed_url}")
            self.logger.debug(f"Embedding model: {self.embedding_model}")
            self.logger.debug(f"Text for embedding: {text[:100]}...") # Log first 100 chars

            r = self.http_session.post(self.embed_url, json=payload, timeout=self.timeout)

            self.logger.debug(f"Embedding response status: {r.status_code}")
            r.raise_for_status()

            data = r.json()
            embeddings = data.get("embedding")

            if not embeddings:
                raise ValueError("No embedding found in Ollama API response.")

            # Store in cache
            self._embedding_cache.put(text, embeddings)
            return embeddings
            
        except requests.exceptions.Timeout:
            self.logger.error(f"Embedding request timeout after {self.timeout}s")
            raise
        except requests.exceptions.ConnectionError:
            self.logger.error(f"Connection error: Cannot connect to Ollama for embeddings at {self.embed_url}")
            self.logger.error("Make sure Ollama is running: 'ollama serve'")
            raise
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"Ollama Embedding API Error (Status {r.status_code}): {e.response.text[:500]}")
            # Check for "model not found" (HTTP 404) for embedding model
            if r.status_code == 404 and "model not found" in e.response.text.lower():
                self.logger.warning(f"Embedding model '{self.embedding_model}' not found. Attempting to pull...")
                if self._pull_model(self.embedding_model):
                    self.logger.info(f"Embedding model '{self.embedding_model}' pulled successfully. Retrying embedding request...")
                    try:
                        r = self.http_session.post(self.embed_url, json=payload, timeout=self.timeout)
                        r.raise_for_status()
                        data = r.json()
                        embeddings = data.get("embedding")
                        if not embeddings:
                            raise ValueError("No embedding found in Ollama API response after retry.")
                        return embeddings
                    except Exception as retry_e:
                        self.logger.error(f"Retry after embedding model pull failed for '{self.embedding_model}': {retry_e}")
                        raise
                else:
                    self.logger.error(f"Failed to pull embedding model '{self.embedding_model}'. Cannot generate embeddings.")
                    raise
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in embedding API call: {str(e)}", e)
            raise