import json
import requests
import traceback
from typing import Dict, List, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.utils.core.agent_logger import AgentLogger # Assuming logger is passed

class OllamaClient:
    def __init__(self, url: str, model: str, timeout: int, logger: AgentLogger, config: Dict):
        self.url = f"{url}/api/chat"
        self.model = model
        self.timeout = timeout
        self.logger = logger
        self.config = config # Store config for retry parameters

        # Configure retry strategy
        max_retries = self.config.get("ollama_max_retries", 3)
        backoff_factor = self.config.get("ollama_backoff_factor", 0.3) # Default backoff factor
        status_forcelist = self.config.get("ollama_retry_status_forcelist", [429, 500, 502, 503, 504])

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            allowed_methods=["POST"], # Only retry POST requests to chat endpoint
            raise_on_status=False # Don't raise on first error, let adapter retry
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.http_session = requests.Session()
        self.http_session.mount("http://", adapter)
        self.http_session.mount("https://", adapter)

    def chat(self, messages: List[Dict], tools: List[Dict]) -> tuple[Dict, Dict]:
        """
        Returns (response_data, usage_stats)
        Enhanced with better error handling and logging, and retry mechanism.
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 4096
            }
        }
        
        try:
            # Log request details
            self.logger.debug(f"Sending request to {self.url}")
            self.logger.debug(f"Model: {self.model}")
            self.logger.debug(f"Messages count: {len(messages)}")
            self.logger.debug(f"Tools count: {len(tools)}")
            
            # Log tool names for debugging
            tool_names = [t["function"]["name"] for t in tools]
            self.logger.debug(f"Available tools: {', '.join(tool_names)}")
            
            # Make request using session with retry logic
            r = self.http_session.post(self.url, json=payload, timeout=self.timeout)
            
            # Log response status
            self.logger.debug(f"Response status: {r.status_code}")
            
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
            
            return data, usage
            
        except requests.exceptions.Timeout:
            self.logger.error(f"Request timeout after {self.timeout}s")
            raise
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection error: Cannot connect to Ollama at {self.url}")
            self.logger.error("Make sure Ollama is running: 'ollama serve'")
            raise
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"Ollama API Error (Status {r.status_code}): {e.response.text[:500]}")
            # Further check for tool not found if it's a 400 or similar
            if "tool" in e.response.text.lower() and "not found" in e.response.text.lower():
                self.logger.warning("The model tried to use a tool that doesn't exist.")
                # Log available tools for debugging
                self.logger.warning(f"Available tools: {', '.join(tool_names)}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error in API call: {str(e)}", e)
            raise
