"""
Language Manager Service

Enforces English standardization across all system processes.
Handles automatic translation of inputs and ensuring outputs remain in English.
"""

import logging
from typing import Any, Optional, Tuple

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
        Detects language and translates to English ONLY if necessary.
        Returns (english_text, detected_lang_code).
        """
        if not text or not text.strip():
            return text, "en"

        # F33: Refined heuristic. If it has very few non-ASCII chars, assume English passthrough
        non_ascii_count = sum(1 for c in text if ord(c) > 127)
        is_likely_not_en = non_ascii_count > 2 # Allow for a few special chars without translating

        if not is_likely_not_en:
            return text, "en"

        logger.info(f"Detecting non-English input ({non_ascii_count} non-ascii). Translating...")

        try:
            from backend.utils.core.llm.prompt_loader import PromptLoader

            loader = PromptLoader()
            prompts = loader.load_prompt("core/services.yaml")

            system = prompts.get("translation_standardization", {}).get("system", "")
            user_template = prompts.get("translation_standardization", {}).get("user", "")
            user = user_template.format(text=text)

            # Use a faster model for translation if available, otherwise default
            client = self.llm_provider.get_client("orchestration")
            response, _ = await client.achat(
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}], tools=[]
            )
            raw_translated = response.get("message", {}).get("content", text).strip()

            # F33: Radical cleaning of conversational noise
            # 1. Remove common SLM preambles
            noise_patterns = [
                "Understood", "Please provide", "Here is", "Translation:",
                "The translation is", "Translated text:", "Certainly", "Sure"
            ]

            cleaned = raw_translated
            for pattern in noise_patterns:
                if cleaned.startswith(pattern):
                    # Try to find the actual content after a colon or just remove the line
                    if ":" in cleaned:
                        cleaned = cleaned.split(":", 1)[1].strip()
                    else:
                        lines = cleaned.split("\n")
                        if len(lines) > 1:
                            cleaned = "\n".join(lines[1:]).strip()

            # 2. Strip quotes if the model wrapped the translation
            if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
                cleaned = cleaned[1:-1].strip()

            # Final check: if cleaning emptied it or it still looks like noise, use original text
            if not cleaned or "provide the text" in cleaned.lower():
                logger.warning(f"Translation seems invalid, falling back to original: {cleaned}")
                return text, "error"

            return cleaned, "detected"
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
                "content": "Translate the following system prompt to English. Maintain all technical placeholders like {{variable}} or {placeholder}. Return ONLY the English version.",
            },
            {"role": "user", "content": system_prompt},
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
