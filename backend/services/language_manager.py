"""
Language Manager Service

Enforces English standardization across all system processes.
Handles automatic translation of inputs and ensuring outputs remain in English.
"""

import logging
import json
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class LanguageManager:
    """
    Service to ensure all internal processing happens in English.
    Mandatory for SLM/LLM reasoning accuracy.
    """

    def __init__(self, llm_provider: Any):
        self.llm_provider = llm_provider

    async def ensure_english_input(self, text: str) -> Tuple[str, str]:
        """
        Detects language and translates to English if necessary.
        Returns (english_text, detected_lang_code).
        """
        if not text or not text.strip():
            return text, "en"

        # Basic heuristic for non-English detection (high non-ASCII count)
        is_likely_not_en = any(ord(c) > 127 for c in text[:500])
        
        if not is_likely_not_en:
            # We still might want to "standardize" or "refine" the prompt even if it's English
            return text, "en"

        logger.info(f"Detecting non-English input. Translating to English for internal processing...")
        
        prompt = [
            {
                "role": "system",
                "content": "You are a translation and prompt standardization expert. Translate the user's request to English if it's in another language. Return ONLY the translated English text. Maintain technical terms exactly as they are."
            },
            {"role": "user", "content": text}
        ]

        try:
            # Use a faster model for translation if available, otherwise default
            client = self.llm_provider.get_client("orchestration")
            response, _ = await client.achat(prompt, tools=[])
            translated = response.get("message", {}).get("content", text).strip()
            return translated, "detected" # We don't necessarily need the exact code for internal use
        except Exception as e:
            logger.error(f"Automatic translation failed: {e}")
            return text, "error"

    async def standardize_prompt(self, system_prompt: str) -> str:
        """
        Validates that a system prompt is in English. 
        If not, translates it automatically.
        """
        if not system_prompt:
            return system_prompt

        is_likely_not_en = any(ord(c) > 127 for c in system_prompt[:500])
        if not is_likely_not_en:
            return system_prompt

        logger.warning("Spanish or non-English system prompt detected! Automatically translating to English...")
        
        prompt = [
            {
                "role": "system",
                "content": "Translate the following system prompt to English. Maintain all technical placeholders like {{variable}} or {placeholder}. Return ONLY the English version."
            },
            {"role": "user", "content": system_prompt}
        ]

        try:
            client = self.llm_provider.get_client("orchestration")
            response, _ = await client.achat(prompt, tools=[])
            return response.get("message", {}).get("content", system_prompt).strip()
        except Exception as e:
            logger.error(f"System prompt translation failed: {e}")
            return system_prompt

    def enforce_output_language(self, response: str, target_lang: Optional[str] = None) -> str:
        """
        Ensures output is in English unless explicitly requested otherwise.
        Currently, just returns the response as is (assuming LLM followed system prompt instructions).
        """
        # Logic to translate back to user language could go here IF explicitly requested.
        # Otherwise, the default is English.
        return response
