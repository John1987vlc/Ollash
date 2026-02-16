"""
Documentation Translator

LLM-based translation for README files and code comments
across multiple languages.
"""

from typing import Any, Dict, Optional

from backend.utils.core.agent_logger import AgentLogger
from backend.utils.core.llm_response_parser import LLMResponseParser


# Language codes and names
SUPPORTED_LANGUAGES: Dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ru": "Russian",
    "ar": "Arabic",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "hi": "Hindi",
}


class DocTranslator:
    """Translates documentation and code comments using LLM.

    Used in the DocumentationTranslationPhase to generate
    README.{lang}.md files for configured target languages.
    """

    def __init__(
        self,
        llm_client: Any,
        logger: AgentLogger,
        response_parser: Optional[LLMResponseParser] = None,
    ):
        self.llm_client = llm_client
        self.logger = logger
        self.response_parser = response_parser

    async def translate_readme(self, content: str, target_lang: str) -> str:
        """Translate a README document to a target language.

        Preserves markdown formatting, code blocks, and URLs.
        """
        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        prompt = f"""Translate the following README document to {lang_name}.

IMPORTANT RULES:
- Preserve ALL markdown formatting (headers, lists, links, code blocks)
- Do NOT translate text inside code blocks (``` ... ```)
- Do NOT translate URLs, file paths, or package names
- Do NOT translate variable names or command-line examples
- Keep the same document structure
- Translate comments in code examples if they are in a natural language

README to translate:

{content}

Translated README in {lang_name}:"""

        try:
            response = await self._call_llm(prompt)
            if response:
                self.logger.info(f"Translated README to {lang_name} ({len(response)} chars)")
                return response
        except Exception as e:
            self.logger.error(f"Failed to translate README to {lang_name}: {e}")

        return content  # Return original on failure

    async def translate_code_comments(self, content: str, source_lang: str, target_lang: str) -> str:
        """Translate inline comments and docstrings in source code.

        Preserves code logic, only translates natural language in comments.
        """
        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        prompt = f"""Translate ONLY the comments and docstrings in the following code to {lang_name}.

CRITICAL RULES:
- Do NOT modify any actual code
- Only translate text in comments (# ..., // ..., /* ... */) and docstrings
- Preserve exact indentation and formatting
- If a comment contains technical terms, keep them in English with translation in parentheses

Code:

{content}

Code with translated comments:"""

        try:
            response = await self._call_llm(prompt)
            if response:
                return response
        except Exception as e:
            self.logger.error(f"Failed to translate comments to {lang_name}: {e}")

        return content

    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Call the LLM client for translation."""
        messages = [{"role": "user", "content": prompt}]

        try:
            response = self.llm_client.chat(messages=messages)
            if response and "message" in response:
                return response["message"].get("content", "")
        except Exception as e:
            self.logger.error(f"LLM translation call failed: {e}")

        return None

    def get_output_filename(self, original_name: str, target_lang: str) -> str:
        """Generate translated file name (e.g., README.es.md)."""
        from pathlib import Path

        p = Path(original_name)
        return f"{p.stem}.{target_lang}{p.suffix}"

    def get_supported_languages(self) -> Dict[str, str]:
        """Return supported language codes and names."""
        return dict(SUPPORTED_LANGUAGES)
