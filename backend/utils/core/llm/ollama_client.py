import asyncio

import aiohttp
import requests


class OllamaClient:
    def __init__(self, url, model, timeout, logger, config, llm_recorder, model_health_monitor=None):
        self.base_url = str(url).rstrip("/")
        self.chat_url = f"{self.base_url}/api/chat"
        self.model = model
        self.logger = logger
        self.config = config
        self._llm_recorder = llm_recorder
        self.timeout = timeout
        self.http_session = requests.Session()
        self._aiohttp_session = None
        self._aiohttp_session_lock = asyncio.Lock()
        self._gpu_limiter_enabled = False

    async def _get_aiohttp_session(self):
        if self._aiohttp_session is None or self._aiohttp_session.closed:
            async with self._aiohttp_session_lock:
                if self._aiohttp_session is None or self._aiohttp_session.closed:
                    self._aiohttp_session = aiohttp.ClientSession()
        return self._aiohttp_session

    async def achat(self, messages, tools=None, options_override=None, context=None):
        import time
        tools = tools or []
        if context is None:
            context = getattr(self, "_session_context", None)
        opts = {"temperature": 0.1, "num_ctx": 32768, "keep_alive": "5m"}
        if options_override:
            opts.update(options_override)
        if hasattr(self, "_keep_alive"):
            opts["keep_alive"] = self._keep_alive
        
        # Record request
        if self._llm_recorder:
            self._llm_recorder.record_request(self.model, messages, tools, opts)

        payload = {"model": self.model, "messages": messages, "tools": tools, "stream": False, "options": opts}
        if context:
            payload["context"] = context
        
        start_time = time.time()
        session = await self._get_aiohttp_session()
        try:
            async with session.post(self.chat_url, json=payload, timeout=self.timeout) as resp:
                data = await resp.json()
                latency = time.time() - start_time
                res = data.copy()
                res["content"] = data.get("message", {}).get("content", "")
                
                usage = {
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0)
                }

                if self._llm_recorder:
                    self._llm_recorder.record_response(self.model, res, usage, latency, True)

                if "context" in data:
                    res["context"] = data["context"]
                return res, usage
        except Exception as e:
            if self._llm_recorder:
                self._llm_recorder.record_response(self.model, {}, {}, time.time() - start_time, False, str(e))
            raise

    def chat(self, messages, tools=None, options_override=None, context=None):
        import time
        tools = tools or []
        if context is None:
            context = getattr(self, "_session_context", None)
        opts = {"temperature": 0.1, "num_ctx": 32768, "keep_alive": "5m"}
        if options_override:
            opts.update(options_override)
        if hasattr(self, "_keep_alive"):
            opts["keep_alive"] = self._keep_alive

        # Record request
        if self._llm_recorder:
            self._llm_recorder.record_request(self.model, messages, tools, opts)

        payload = {"model": self.model, "messages": messages, "tools": tools, "stream": False, "options": opts}
        if context:
            payload["context"] = context
        
        start_time = time.time()
        try:
            r = self.http_session.post(self.chat_url, json=payload, timeout=self.timeout)
            data = r.json()
            latency = time.time() - start_time
            res = data.copy()
            res["content"] = data.get("message", {}).get("content", "")
            
            usage = {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0)
            }

            if self._llm_recorder:
                self._llm_recorder.record_response(self.model, res, usage, latency, True)

            if "context" in data:
                res["context"] = data["context"]
            return res, usage
        except Exception as e:
            if self._llm_recorder:
                self._llm_recorder.record_response(self.model, {}, {}, time.time() - start_time, False, str(e))
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
