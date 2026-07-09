import json
import asyncio
import aiohttp
import requests
import time
import math
import ollama
from typing import Optional
from backend.utils.core.llm.token_tracker import TokenTracker
from backend.utils.core.system.execution_bridge import bridge
from backend.utils.core.system.network_monitor import network_monitor as _net_monitor



def _hash_embedding(text: str, dim: int = 384) -> list[float]:
    """Fallback: deterministic char-frequency embedding, no external deps."""
    vec = [0.0] * dim
    for i, ch in enumerate(text[:4096]):
        vec[ord(ch) % dim] += 1.0
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class OllamaClient:
    def __init__(
        self,
        url,
        model,
        timeout,
        logger,
        config,
        llm_recorder,
        model_health_monitor=None,
        token_tracker: Optional[TokenTracker] = None,
    ):
        self.base_url = str(url).rstrip("/")
        self.chat_url = f"{self.base_url}/api/chat"
        self.model = model.strip()
        self.logger = logger
        self.config = config
        self._llm_recorder = llm_recorder
        self.token_tracker = token_tracker
        self.timeout = timeout
        self._client = ollama.Client(host=self.base_url, timeout=self.timeout)
        self._aclient = ollama.AsyncClient(host=self.base_url, timeout=self.timeout)
        self.http_session = requests.Session()
        self._aiohttp_session = None
        self._aiohttp_session_lock = asyncio.Lock()
        self._gpu_limiter_enabled = False
        self._embedding_model = "nomic-embed-text"  # overridable via set_embedding_model()


    async def _get_aiohttp_session(self):
        # Check if current loop is different from session's loop
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            return None  # Should not happen in async context

        if self._aiohttp_session is not None:
            # Check if session loop is closed or different
            sess_loop = getattr(self._aiohttp_session, "_loop", None) or getattr(self._aiohttp_session, "loop", None)

            if self._aiohttp_session.closed or sess_loop != current_loop:
                if not self._aiohttp_session.closed:
                    await self._aiohttp_session.close()
                self._aiohttp_session = None

        if self._aiohttp_session is None:
            async with self._aiohttp_session_lock:
                if self._aiohttp_session is None:
                    self._aiohttp_session = aiohttp.ClientSession()
        return self._aiohttp_session

    async def _check_saturation(self, messages: list) -> None:
        """Publish a context_saturation_alert event if prompt nears the model's window."""
        try:
            from backend.utils.core.llm.context_saturation import check_context_saturation

            full_text = " ".join(m.get("content", "") for m in messages if isinstance(m, dict))
            warning = check_context_saturation(full_text, self.model)
            if warning and self.logger.event_publisher:
                await self.logger.event_publisher.publish(
                    "context_saturation_alert",
                    event_data={"model": self.model, "warning": warning},
                )
        except Exception:
            pass  # Saturation check must never abort LLM calls

    async def achat(self, messages, tools=None, options_override=None, context=None):
        tools = tools or []
        if context is None:
            context = getattr(self, "_session_context", None)

        # F31: Lowered context limits
        default_ctx = self.config.get("max_context_tokens", 8192)
        default_predict = self.config.get("max_output_tokens", 2048)

        opts = {"temperature": 0.1, "num_ctx": default_ctx, "num_predict": default_predict, "keep_alive": "5m"}
        # Top-level Ollama payload keys (e.g. "think": False for Qwen3) must NOT go into "options".
        # Extract them before merging the rest into opts.
        _TOP_LEVEL_KEYS = {"think"}
        top_level_extras: dict = {}
        if options_override:
            override_copy = dict(options_override)
            for k in _TOP_LEVEL_KEYS:
                if k in override_copy:
                    top_level_extras[k] = override_copy.pop(k)
            opts.update(override_copy)
        if hasattr(self, "_keep_alive"):
            opts["keep_alive"] = self._keep_alive

        # Feature 6: Context saturation check
        await self._check_saturation(messages)

        payload = {"model": self.model, "messages": messages, "tools": tools, "stream": False, "options": opts}
        payload.update(top_level_extras)
        if context:
            payload["context"] = context

        self.logger.debug(
            f"[OllamaClient] Calling model: {self.model} | num_ctx={opts['num_ctx']}, num_predict={opts['num_predict']}"
        )
        if self.logger.event_publisher:
            await self.logger.event_publisher.publish("llm_request", {"model": self.model, "payload": payload})

        if self._llm_recorder:
            self._llm_recorder.record_request(self.model, messages, tools, opts)

        start_time = time.time()
        try:
            self.logger.debug(f"[OllamaClient] Sending chat request via official AsyncClient to {self.model}")
            
            # Extract keep_alive from options as expected by ollama.AsyncClient
            keep_alive = opts.pop("keep_alive", "5m")
            
            # Call AsyncClient chat
            kwargs = {}
            if top_level_extras:
                kwargs.update(top_level_extras)
                
            response = await self._aclient.chat(
                model=self.model,
                messages=messages,
                tools=tools,
                options=opts,
                keep_alive=keep_alive,
                **kwargs
            )
            _net_monitor.record(self.chat_url, "POST", 200)
            
            # Convert response to dictionary to preserve compatibility
            if hasattr(response, "model_dump"):
                data = response.model_dump()
            elif hasattr(response, "dict"):
                data = response.dict()
            else:
                data = dict(response)

            latency = time.time() - start_time
            self.logger.debug(f"[OllamaClient] Response received in {latency:.2f}s")

            # Debug logging after response
            if self.logger.event_publisher:
                await self.logger.event_publisher.publish("llm_response", {"model": self.model, "response": data})

            res = data.copy()
            message = data.get("message", {})
            res["content"] = message.get("content", "")
            res["tool_calls"] = message.get("tool_calls", [])

            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }

            self.logger.debug(f"[OllamaClient] Tokens: {prompt_tokens} prompt, {completion_tokens} completion")

            if self.token_tracker:
                self.token_tracker.add_usage(prompt_tokens, completion_tokens)

            if self._llm_recorder:
                self._llm_recorder.record_response(self.model, res, usage, latency, True)

            from backend.utils.core.llm.call_log import llm_call_log
            llm_call_log.record(self.model, prompt_tokens, completion_tokens, latency * 1000, True)

            if "context" in data:
                res["context"] = data["context"]
            return res, usage
        except Exception as e:
            self.logger.debug(f"[OllamaClient] ERROR in chat: {e}")
            latency = time.time() - start_time
            if self._llm_recorder:
                self._llm_recorder.record_response(self.model, {}, {}, latency, False, str(e))
            from backend.utils.core.llm.call_log import llm_call_log
            llm_call_log.record(self.model, 0, 0, latency * 1000, False, str(e))
            raise

    def chat(self, messages, tools=None, options_override=None, context=None):
        """Synchronous chat method. USES bridge.run internally for robust async management."""
        return bridge.run(self.achat(messages, tools, options_override, context))

    async def stream_chat(
        self,
        messages: list,
        tools: list = None,
        chunk_callback=None,
        options_override: dict | None = None,
    ) -> tuple:
        """Streaming chat: calls chunk_callback(str) for each token chunk."""

        # F31: Increase default context to 32k
        default_ctx = self.config.get("max_context_tokens", 32768)
        opts = {"temperature": 0.1, "num_ctx": default_ctx, "keep_alive": "5m"}
        if options_override:
            opts.update(options_override)
        if hasattr(self, "_keep_alive"):
            opts["keep_alive"] = self._keep_alive

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": opts,
        }
        if tools:
            payload["tools"] = tools

        # Debug logging before request
        if self.logger.event_publisher:
            self.logger.event_publisher.publish_sync("llm_request", {"model": self.model, "payload": payload})

        if self._llm_recorder:
            self._llm_recorder.record_request(self.model, messages, [], opts)

        start_time = time.time()
        full_content = ""
        full_tool_calls = []
        usage: dict = {"prompt_tokens": 0, "completion_tokens": 0}

        try:
            keep_alive = opts.pop("keep_alive", "5m")
            response = await self._aclient.chat(
                model=self.model,
                messages=messages,
                tools=tools,
                options=opts,
                keep_alive=keep_alive,
                stream=True
            )
            _net_monitor.record(self.chat_url, "POST", 200)

            async for chunk in response:
                if hasattr(chunk, "model_dump"):
                    chunk_data = chunk.model_dump()
                elif hasattr(chunk, "dict"):
                    chunk_data = chunk.dict()
                else:
                    chunk_data = dict(chunk)

                # Propagate Ollama server-side errors immediately
                if "error" in chunk_data:
                    raise RuntimeError(f"Ollama error: {chunk_data['error']}")

                chunk_content = chunk_data.get("message", {}).get("content", "")
                if chunk_content:
                    full_content += chunk_content
                    if chunk_callback is not None:
                        if asyncio.iscoroutinefunction(chunk_callback):
                            await chunk_callback(chunk_content)
                        else:
                            chunk_callback(chunk_content)

                # Capture native tool calls from stream
                tc = chunk_data.get("message", {}).get("tool_calls")
                if tc:
                    full_tool_calls.extend(tc)

                if chunk_data.get("done"):
                    usage = {
                        "prompt_tokens": chunk_data.get("prompt_eval_count", 0),
                        "completion_tokens": chunk_data.get("eval_count", 0),
                    }
                    if self.token_tracker:
                        self.token_tracker.add_usage(usage["prompt_tokens"], usage["completion_tokens"])

            latency = time.time() - start_time

            # Debug logging after response
            result = {"content": full_content, "tool_calls": full_tool_calls}
            if self.logger.event_publisher:
                self.logger.event_publisher.publish_sync("llm_response", {"model": self.model, "response": result})

            if self._llm_recorder:
                self._llm_recorder.record_response(self.model, result, usage, latency, True)
            return result, usage

        except asyncio.TimeoutError:
            latency = time.time() - start_time
            if self._llm_recorder:
                self._llm_recorder.record_response(self.model, {}, {}, latency, False, "Timeout")
            return {"content": full_content}, usage
        except Exception as exc:
            latency = time.time() - start_time
            if self._llm_recorder:
                self._llm_recorder.record_response(self.model, {}, {}, latency, False, str(exc))
            raise

    def set_session_context(self, context):
        self._session_context = context

    def set_keep_alive(self, keep_alive):
        self._keep_alive = keep_alive

    def unload_model(self, model=None):
        target = model or self.model
        try:
            self.logger.debug(f"[OllamaClient] Unloading model {target} via official Client")
            self._client.generate(model=target, keep_alive=0)
        except Exception as e:
            self.logger.debug(f"[OllamaClient] unload_model failed: {e}")

    def set_embedding_model(self, model_name: str) -> None:
        self._embedding_model = model_name

    def get_embedding(self, text: str, max_chars: int = None) -> list[float]:
        """Return embedding vector via Ollama /api/embed; falls back to hash embedding."""
        if max_chars:
            text = text[:max_chars]
        try:
            self.logger.debug(f"[OllamaClient] Fetching embedding for text via official Client")
            resp = self._client.embed(model=self._embedding_model, input=text)
            _net_monitor.record(f"{self.base_url}/api/embed", "POST", 200)
            
            # Convert response to dictionary to preserve compatibility
            if hasattr(resp, "model_dump"):
                resp_data = resp.model_dump()
            elif hasattr(resp, "dict"):
                resp_data = resp.dict()
            else:
                resp_data = dict(resp)
                
            embeddings = resp_data.get("embeddings", [[]])[0]
            if embeddings:
                return embeddings
        except Exception as e:
            self.logger.debug(f"[OllamaClient] get_embedding failed ({e}), using hash fallback")
        return _hash_embedding(text)

    async def aget_embedding(self, text: str) -> list[float]:
        """Async embedding via Ollama /api/embed; falls back to hash embedding."""
        try:
            self.logger.debug(f"[OllamaClient] Fetching embedding for text via official AsyncClient")
            resp = await self._aclient.embed(model=self._embedding_model, input=text)
            _net_monitor.record(f"{self.base_url}/api/embed", "POST", 200)
            
            # Convert response to dictionary to preserve compatibility
            if hasattr(resp, "model_dump"):
                resp_data = resp.model_dump()
            elif hasattr(resp, "dict"):
                resp_data = resp.dict()
            else:
                resp_data = dict(resp)
                
            embeddings = resp_data.get("embeddings", [[]])[0]
            if embeddings:
                return embeddings
        except Exception as e:
            self.logger.debug(f"[OllamaClient] aget_embedding failed ({e}), using hash fallback")
        return _hash_embedding(text)

    async def close(self):
        """Properly closes the aiohttp session."""
        if self._aiohttp_session and not self._aiohttp_session.closed:
            await self._aiohttp_session.close()
            self.logger.debug(f"OllamaClient session for model {self.model} closed.")
