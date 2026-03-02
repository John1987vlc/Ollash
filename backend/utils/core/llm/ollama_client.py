import json
import asyncio
import aiohttp
import requests
import time
from typing import Optional
from backend.utils.core.llm.token_tracker import TokenTracker


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
        self.http_session = requests.Session()
        self._aiohttp_session = None
        self._aiohttp_session_lock = asyncio.Lock()
        self._gpu_limiter_enabled = False

    async def _get_aiohttp_session(self):
        # Check if current loop is different from session's loop
        current_loop = asyncio.get_running_loop()

        if self._aiohttp_session is not None:
            # Check if session loop is closed or different
            if self._aiohttp_session.closed or self._aiohttp_session._loop != current_loop:
                self._aiohttp_session = None

        if self._aiohttp_session is None:
            async with self._aiohttp_session_lock:
                if self._aiohttp_session is None:
                    self._aiohttp_session = aiohttp.ClientSession()
        return self._aiohttp_session

    def _check_saturation(self, messages: list) -> None:
        """Publish a context_saturation_alert event if prompt nears the model's window."""
        try:
            from backend.utils.core.llm.context_saturation import check_context_saturation

            full_text = " ".join(m.get("content", "") for m in messages if isinstance(m, dict))
            warning = check_context_saturation(full_text, self.model)
            if warning and self.logger.event_publisher:
                self.logger.event_publisher.publish(
                    "context_saturation_alert",
                    model=self.model,
                    warning=warning,
                )
        except Exception:
            pass  # Saturation check must never abort LLM calls

    async def achat(self, messages, tools=None, options_override=None, context=None):

        tools = tools or []
        if context is None:
            context = getattr(self, "_session_context", None)
        opts = {"temperature": 0.1, "num_ctx": self.config.get("max_context_tokens", 8000), "keep_alive": "5m"}
        if options_override:
            opts.update(options_override)
        if hasattr(self, "_keep_alive"):
            opts["keep_alive"] = self._keep_alive

        # Feature 6: Context saturation check
        self._check_saturation(messages)

        payload = {"model": self.model, "messages": messages, "tools": tools, "stream": False, "options": opts}
        if context:
            payload["context"] = context

        # Debug logging before request
        if self.logger.event_publisher:
            self.logger.event_publisher.publish("llm_request", {"model": self.model, "payload": payload})
        try:
            self.logger.debug(f"DEBUG - LLM Payload for {self.model}: {json.dumps(payload, indent=2)}")
        except (TypeError, ValueError):
            self.logger.debug(f"DEBUG - LLM Payload for {self.model}: (not serializable)")

        if self._llm_recorder:
            self._llm_recorder.record_request(self.model, messages, tools, opts)

        start_time = time.time()
        session = await self._get_aiohttp_session()
        request_timeout = aiohttp.ClientTimeout(total=self.timeout)

        try:
            async with session.post(self.chat_url, json=payload, timeout=request_timeout) as resp:
                data = await resp.json()
                latency = time.time() - start_time

                # Debug logging after response
                if self.logger.event_publisher:
                    self.logger.event_publisher.publish("llm_response", {"model": self.model, "response": data})
                self.logger.debug(f"DEBUG - LLM Response: {json.dumps(data, indent=2)}")

                res = data.copy()
                res["content"] = data.get("message", {}).get("content", "")

                prompt_tokens = data.get("prompt_eval_count", 0)
                completion_tokens = data.get("eval_count", 0)
                usage = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }

                if self.token_tracker:
                    self.token_tracker.add_usage(prompt_tokens, completion_tokens)

                if self._llm_recorder:
                    self._llm_recorder.record_response(self.model, res, usage, latency, True)

                if "context" in data:
                    res["context"] = data["context"]
                return res, usage
        except asyncio.TimeoutError:
            latency = time.time() - start_time
            if self._llm_recorder:
                self._llm_recorder.record_response(self.model, {}, {}, latency, False, "Timeout")
            return {"error": "Ollama request timed out", "message": {"content": ""}}, {
                "prompt_tokens": 0,
                "completion_tokens": 0,
            }
        except Exception as e:
            latency = time.time() - start_time
            if self._llm_recorder:
                self._llm_recorder.record_response(self.model, {}, {}, latency, False, str(e))
            raise

    def chat(self, messages, tools=None, options_override=None, context=None):

        tools = tools or []
        if context is None:
            context = getattr(self, "_session_context", None)
        opts = {"temperature": 0.1, "num_ctx": self.config.get("max_context_tokens", 8000), "keep_alive": "5m"}
        if options_override:
            opts.update(options_override)
        if hasattr(self, "_keep_alive"):
            opts["keep_alive"] = self._keep_alive

        # Feature 6: Context saturation check
        self._check_saturation(messages)

        payload = {"model": self.model, "messages": messages, "tools": tools, "stream": False, "options": opts}
        if context:
            payload["context"] = context

        # Debug logging before request
        if self.logger.event_publisher:
            self.logger.event_publisher.publish("llm_request", {"model": self.model, "payload": payload})
        try:
            self.logger.debug(f"DEBUG - LLM Payload for {self.model}: {json.dumps(payload, indent=2)}")
        except (TypeError, ValueError):
            self.logger.debug(f"DEBUG - LLM Payload for {self.model}: (not serializable)")

        if self._llm_recorder:
            self._llm_recorder.record_request(self.model, messages, tools, opts)

        start_time = time.time()
        try:
            r = self.http_session.post(self.chat_url, json=payload, timeout=self.timeout)
            data = r.json()
            latency = time.time() - start_time

            # Debug logging after response
            if self.logger.event_publisher:
                self.logger.event_publisher.publish("llm_response", {"model": self.model, "response": data})
            self.logger.debug(f"DEBUG - LLM Response: {json.dumps(data, indent=2)}")

            res = data.copy()
            res["content"] = data.get("message", {}).get("content", "")

            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)
            usage = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}

            if self.token_tracker:
                self.token_tracker.add_usage(prompt_tokens, completion_tokens)

            if self._llm_recorder:
                self._llm_recorder.record_response(self.model, res, usage, latency, True)

            if "context" in data:
                res["context"] = data["context"]
            return res, usage
        except Exception as e:
            if self._llm_recorder:
                self._llm_recorder.record_response(self.model, {}, {}, time.time() - start_time, False, str(e))
            raise

    async def stream_chat(
        self,
        messages: list,
        tools: list = None,
        chunk_callback=None,
        options_override: dict | None = None,
    ) -> tuple:
        """Streaming chat: calls chunk_callback(str) for each token chunk.

        Uses Ollama's NDJSON streaming API (``"stream": true``).  Each line is
        a JSON object; non-empty ``message.content`` values are forwarded to
        *chunk_callback*.  If *chunk_callback* is an async coroutine function
        it is awaited; otherwise called synchronously.

        Returns:
            ``(result_dict, usage_dict)`` \u2014 same shape as ``achat()``.
        """

        opts = {"temperature": 0.1, "num_ctx": self.config.get("max_context_tokens", 8000), "keep_alive": "5m"}
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
            self.logger.event_publisher.publish("llm_request", {"model": self.model, "payload": payload})
        try:
            self.logger.debug(f"DEBUG - LLM Payload for {self.model}: {json.dumps(payload, indent=2)}")
        except (TypeError, ValueError):
            self.logger.debug(f"DEBUG - LLM Payload for {self.model}: (not serializable)")

        if self._llm_recorder:
            self._llm_recorder.record_request(self.model, messages, [], opts)

        start_time = time.time()
        full_content = ""
        full_tool_calls = []
        usage: dict = {"prompt_tokens": 0, "completion_tokens": 0}

        session = await self._get_aiohttp_session()
        request_timeout = aiohttp.ClientTimeout(total=self.timeout)

        data = {}
        try:
            async with session.post(self.chat_url, json=payload, timeout=request_timeout) as resp:
                async for raw_line in resp.content:
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        data = json.loads(raw_line)
                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            full_content += chunk
                            if chunk_callback is not None:
                                if asyncio.iscoroutinefunction(chunk_callback):
                                    await chunk_callback(chunk)
                                else:
                                    chunk_callback(chunk)
                        # Capture native tool calls from stream
                        tc = data.get("message", {}).get("tool_calls")
                        if tc:
                            full_tool_calls.extend(tc)

                        if data.get("done"):
                            usage = {
                                "prompt_tokens": data.get("prompt_eval_count", 0),
                                "completion_tokens": data.get("eval_count", 0),
                            }
                            if self.token_tracker:
                                self.token_tracker.add_usage(usage["prompt_tokens"], usage["completion_tokens"])
                    except Exception:
                        continue

            latency = time.time() - start_time

            # Debug logging after response
            if self.logger.event_publisher:
                self.logger.event_publisher.publish("llm_response", {"model": self.model, "response": data})
            self.logger.debug(f"DEBUG - LLM Response: {json.dumps(data, indent=2)}")

            result = {"content": full_content, "tool_calls": full_tool_calls}
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
        pass

    def get_embedding(self, text, max_chars=None):
        return [0.0] * 384

    async def aget_embedding(self, text):
        return [0.0] * 384

    async def close(self):
        """Properly closes the aiohttp session."""
        if self._aiohttp_session and not self._aiohttp_session.closed:
            await self._aiohttp_session.close()
            self.logger.debug(f"OllamaClient session for model {self.model} closed.")
