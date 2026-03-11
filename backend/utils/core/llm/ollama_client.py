import json
import asyncio
import aiohttp
import requests
import time
from typing import Optional
from backend.utils.core.llm.token_tracker import TokenTracker
from backend.utils.core.system.execution_bridge import bridge


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
        if options_override:
            opts.update(options_override)
        if hasattr(self, "_keep_alive"):
            opts["keep_alive"] = self._keep_alive

        # Feature 6: Context saturation check
        await self._check_saturation(messages)

        payload = {"model": self.model, "messages": messages, "tools": tools, "stream": False, "options": opts}
        if context:
            payload["context"] = context

        # Debug logging before request
        print(f"\n[OllamaClient] Calling model: {self.model} (SYNC via requests) ...")
        print(f"[OllamaClient] Options: num_ctx={opts['num_ctx']}, num_predict={opts['num_predict']}")
        if self.logger.event_publisher:
            await self.logger.event_publisher.publish("llm_request", {"model": self.model, "payload": payload})

        try:
            self.logger.debug(f"DEBUG - LLM Payload for {self.model}: {json.dumps(payload, indent=2)}")
        except (TypeError, ValueError):
            self.logger.debug(f"DEBUG - LLM Payload for {self.model}: (not serializable)")

        if self._llm_recorder:
            self._llm_recorder.record_request(self.model, messages, tools, opts)

        start_time = time.time()

        # F33: Use synchronous requests in a thread pool to avoid aiohttp hangs
        loop = asyncio.get_event_loop()

        def _do_post():
            return self.http_session.post(self.chat_url, json=payload, timeout=self.timeout)

        print(f"[OllamaClient] Sending SYNC POST to {self.chat_url} ...")
        try:
            resp = await loop.run_in_executor(None, _do_post)
            print(f"[OllamaClient] Response status: {resp.status_code}")

            data = resp.json()
            latency = time.time() - start_time

            print(f"[OllamaClient] Received response in {latency:.2f}s")

            # Debug logging after response
            if self.logger.event_publisher:
                await self.logger.event_publisher.publish("llm_response", {"model": self.model, "response": data})
            self.logger.debug(f"DEBUG - LLM Response: {json.dumps(data, indent=2)}")

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

            print(f"[OllamaClient] Tokens: {prompt_tokens} prompt, {completion_tokens} completion")

            if self.token_tracker:
                self.token_tracker.add_usage(prompt_tokens, completion_tokens)

            if self._llm_recorder:
                self._llm_recorder.record_response(self.model, res, usage, latency, True)

            if "context" in data:
                res["context"] = data["context"]
            return res, usage
        except requests.exceptions.Timeout:
            print("[OllamaClient] TIMEOUT ERROR (Requests)")
            latency = time.time() - start_time
            if self._llm_recorder:
                self._llm_recorder.record_response(self.model, {}, {}, latency, False, "Timeout")
            return {"error": "Ollama request timed out", "message": {"content": ""}}, {
                "prompt_tokens": 0,
                "completion_tokens": 0,
            }
        except Exception as e:
            print(f"[OllamaClient] UNEXPECTED ERROR (Requests): {e}")
            latency = time.time() - start_time
            if self._llm_recorder:
                self._llm_recorder.record_response(self.model, {}, {}, latency, False, str(e))
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
            # Use chunks(1024) or similar if line-based reading hangs with some versions
            async with session.post(self.chat_url, json=payload, timeout=request_timeout) as resp:
                async for line in resp.content:
                    if not line:
                        continue
                    try:
                        line_text = line.decode("utf-8").strip()
                        if not line_text:
                            continue

                        data = json.loads(line_text)
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
                    except Exception as e:
                        self.logger.debug(f"Stream decode error: {e} | Line: {line}")
                        continue

            latency = time.time() - start_time

            # Debug logging after response
            if self.logger.event_publisher:
                self.logger.event_publisher.publish_sync("llm_response", {"model": self.model, "response": data})
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
