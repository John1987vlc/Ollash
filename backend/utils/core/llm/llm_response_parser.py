import json
import re
import unicodedata
from typing import Dict, List, Optional, Tuple, Union

# Card-suit UTF-8-as-latin1 mojibake mapping
_MOJIBAKE_MAP = {
    "\u00e2\u2122\u00a5": "\u2665",  # â™¥ → ♥
    "\u00e2\u2122\u00a6": "\u2666",  # â™¦ → ♦
    "\u00e2\u2122\u00a3": "\u2663",  # â™£ → ♣
    "\u00e2\u2122 ": "\u2660",  # â™  → ♠
}


class LLMResponseParser:
    """Utility class for parsing and cleaning LLM responses."""

    # ------------------------------------------------------------------
    # Unicode / encoding helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _repair_json_string(text: str) -> str:
        """Fix UTF-8-as-latin1 mojibake for common symbols + NFC-normalise."""
        for bad, good in _MOJIBAKE_MAP.items():
            text = text.replace(bad, good)
        return unicodedata.normalize("NFC", text)

    # ------------------------------------------------------------------
    # Think-block removal
    # ------------------------------------------------------------------

    @staticmethod
    def remove_think_blocks(text: str) -> Tuple[str, Optional[str]]:
        """
        Removes <think>/<thinking>/<thinking_process> blocks from LLM output.
        Returns (cleaned_text, thinking_content).
        """
        if not text:
            return "", None

        # Ordered by specificity so the longest tag wins when nested
        _THINK_PATTERN = re.compile(
            r"<(think|thinking|thinking_process)>([\s\S]*?)</\1>",
            re.IGNORECASE,
        )

        thinking: Optional[str] = None
        first_match = _THINK_PATTERN.search(text)
        if first_match:
            thinking = first_match.group(2).strip()

        cleaned = _THINK_PATTERN.sub("", text).strip()
        return cleaned, thinking

    # ------------------------------------------------------------------
    # JSON extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_json(text: str) -> Optional[Union[Dict, List]]:
        """
        Extracts the first JSON object or array found in the text.
        Handles markdown code blocks, custom XML tags, and JS comments.
        """
        if not text:
            return None

        # 1. Remove thinking blocks
        text, _ = LLMResponseParser.remove_think_blocks(text)

        # 2. Try to unwrap custom XML tags like <plan_json>…</plan_json>
        xml_tag_match = re.search(r"<\w+_json>([\s\S]*?)</\w+_json>", text, re.IGNORECASE)
        if xml_tag_match:
            inner = xml_tag_match.group(1).strip()
            # inner may itself contain a markdown fence
            fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", inner, re.IGNORECASE)
            candidate = fence_match.group(1).strip() if fence_match else inner
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        # 3. Try JSON inside markdown code blocks
        json_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if json_block_match:
            candidate = json_block_match.group(1).strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        # 4. Try to find first { or [ and extract via bracket matching
        try:
            start_idx = -1
            for i, char in enumerate(text):
                if char in ("{", "["):
                    start_idx = i
                    break

            if start_idx != -1:
                brace_char = "{" if text[start_idx] == "{" else "["
                end_char = "}" if brace_char == "{" else "]"

                stack = 0
                end_idx = -1
                for i in range(start_idx, len(text)):
                    if text[i] == brace_char:
                        stack += 1
                    elif text[i] == end_char:
                        stack -= 1
                        if stack == 0:
                            end_idx = i
                            break

                if end_idx != -1:
                    candidate = text[start_idx : end_idx + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        # 5. Heuristic repair: strip JS single-line comments and trailing commas
                        repaired = re.sub(r"//[^\n]*", "", candidate)
                        repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
                        try:
                            return json.loads(repaired)
                        except json.JSONDecodeError:
                            pass
        except Exception:
            pass

        return None

    # ------------------------------------------------------------------
    # Code-block extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_raw_content(text: str) -> str:
        """
        Extracts content from markdown code blocks or returns the original text.
        Prioritises the FIRST code block found.
        """
        if not text:
            return ""

        text, _ = LLMResponseParser.remove_think_blocks(text)

        code_match = re.search(r"```(?:\w+)?\n?([\s\S]*?)\n?```", text)
        if code_match:
            return code_match.group(1).strip()

        return text.strip()

    @staticmethod
    def extract_code_block(text: str) -> str:
        """Alias for extract_raw_content for better naming consistency."""
        return LLMResponseParser.extract_raw_content(text)

    @staticmethod
    def extract_single_code_block(text: str) -> str:
        """
        Extracts the first fenced code block, handling unclosed fences gracefully.
        Falls back to the raw (stripped) text when no fence is present.
        """
        if not text:
            return ""

        text, _ = LLMResponseParser.remove_think_blocks(text)

        # Closed block
        match = re.search(r"```(?:\w+)?\n?([\s\S]*?)\n?```", text)
        if match:
            return match.group(1).strip()

        # Unclosed block — take everything after the opening fence
        match = re.search(r"```(?:\w+)?\n?([\s\S]+)", text)
        if match:
            return match.group(1).strip()

        return text.strip()

    @staticmethod
    def extract_code_block_for_file(text: str, file_path: str) -> str:
        """
        Extracts a code block that matches the file's extension.
        Falls back to the LARGEST block when no language match is found.
        """
        if not text:
            return ""

        text, _ = LLMResponseParser.remove_think_blocks(text)

        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""

        # Extension → markdown language identifiers (first alias is canonical)
        lang_map: Dict[str, List[str]] = {
            "py": ["python"],
            "js": ["javascript", "js"],
            "ts": ["typescript", "ts"],
            "tsx": ["tsx", "typescript"],
            "jsx": ["jsx", "javascript"],
            "html": ["html"],
            "css": ["css"],
            "json": ["json"],
            "md": ["markdown", "md"],
            "yml": ["yaml", "yml"],
            "yaml": ["yaml", "yml"],
            "sh": ["bash", "sh", "shell"],
            "go": ["go"],
            "rs": ["rust"],
            "java": ["java"],
        }
        target_langs = lang_map.get(ext, [ext] if ext else [])

        # Try language-specific blocks (first alias wins)
        for lang in target_langs:
            if not lang:
                continue
            pattern = rf"```{re.escape(lang)}\n?([\s\S]*?)\n?```"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # Collect ALL fenced blocks and return the largest one
        all_blocks = re.findall(r"```(?:\w+)?\n?([\s\S]*?)\n?```", text)
        if all_blocks:
            return max(all_blocks, key=len).strip()

        # No fenced block at all → treat raw text as code
        return text.strip()

    # ------------------------------------------------------------------
    # Multi-file extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_multiple_files(text: str) -> Dict[str, str]:
        """
        Parses a multi-file LLM response where files are delimited by
        ``# filename: <path>`` or ``// filename: <path>`` markers followed
        by optional fenced code blocks.

        Returns a mapping of ``{relative_path: file_content}``.
        """
        if not text:
            return {}

        text, _ = LLMResponseParser.remove_think_blocks(text)

        # Regex: optional comment prefix, "filename:" label, capture path
        delimiter_re = re.compile(
            r"(?:^|\n)\s*(?://|#)\s*filename:\s*(\S+)\s*\n",
            re.IGNORECASE,
        )

        files: Dict[str, str] = {}
        positions = [(m.start(), m.group(1), m.end()) for m in delimiter_re.finditer(text)]

        for idx, (start, fname, content_start) in enumerate(positions):
            # Grab text up to next delimiter (or end of string)
            next_start = positions[idx + 1][0] if idx + 1 < len(positions) else len(text)
            segment = text[content_start:next_start]

            # Extract fenced block if present (closed or unclosed)
            closed = re.search(r"```(?:\w+)?\n?([\s\S]*?)\n?```", segment)
            if closed:
                files[fname] = closed.group(1).strip()
            else:
                unclosed = re.search(r"```(?:\w+)?\n?([\s\S]+)", segment)
                if unclosed:
                    files[fname] = unclosed.group(1).strip()
                else:
                    stripped = segment.strip()
                    if stripped:
                        files[fname] = stripped

        return files

    # ------------------------------------------------------------------
    # Thought / action extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_thought_action(text: str) -> Tuple[str, str]:
        """
        Extracts a (thought, action) pair from an LLM response.

        Supported formats (tried in order):
        1. JSON  ``{"thought": "...", "action": "..."}``
        2. XML   ``<thought>...</thought><action>...</action>``
        3. Fallback: entire (cleaned) text becomes the *action*; thought is empty.
        """
        if not text:
            return "", ""

        # Strip internal reasoning blocks first
        cleaned, _ = LLMResponseParser.remove_think_blocks(text)

        if not cleaned:
            return "", ""

        # 1. Try JSON
        parsed = LLMResponseParser.extract_json(cleaned)
        if isinstance(parsed, dict):
            thought = str(parsed.get("thought", ""))
            action = str(parsed.get("action", ""))
            return thought, action

        # 2. Try XML tags
        t_match = re.search(r"<thought>([\s\S]*?)</thought>", cleaned, re.IGNORECASE)
        a_match = re.search(r"<action>([\s\S]*?)</action>", cleaned, re.IGNORECASE)
        if t_match or a_match:
            thought = t_match.group(1).strip() if t_match else ""
            action = a_match.group(1).strip() if a_match else ""
            return thought, action

        # 3. Fallback — plain text → action only
        return "", cleaned.strip()

    # ------------------------------------------------------------------
    # Miscellaneous helpers
    # ------------------------------------------------------------------

    @staticmethod
    def parse_tool_calls(text: str) -> List[Dict]:
        """
        Extracts tool calls from plain-text LLM output (manual fallback for models
        that emit JSON instead of using native function-calling).

        Returns a list of ``{"name": str, "arguments": dict}`` dicts.
        """
        if not text:
            return []

        text, _ = LLMResponseParser.remove_think_blocks(text)

        candidates: List[str] = []
        for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE):
            candidates.append(m.group(1).strip())
        candidates.append(text.strip())

        tool_calls: List[Dict] = []
        seen: set = set()

        for candidate in candidates:
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue

            items = parsed if isinstance(parsed, list) else [parsed]
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = item.get("name") or item.get("function") or item.get("tool")
                args = item.get("arguments") or item.get("parameters") or item.get("args") or {}
                if name and isinstance(args, dict):
                    key = (name, json.dumps(args, sort_keys=True))
                    if key not in seen:
                        seen.add(key)
                        tool_calls.append({"name": name, "arguments": args})

        return tool_calls

    @staticmethod
    def extract_code(text: str, file_path: Optional[str] = None) -> str:
        """
        Robustly extracts code from an LLM response.
        Tries XML tags (<code_created>, <file_content>, etc.) first,
        then markdown blocks, then falls back to raw text.
        """
        if not text:
            return ""

        # 1. Remove thinking blocks
        text, _ = LLMResponseParser.remove_think_blocks(text)

        # 2. Try XML tags specifically used in prompts
        tags = ["code_created", "file_content", "code_fixed", "repaired_code"]
        for tag in tags:
            # 2a. Try closed tag first (most reliable)
            closed_pattern = rf"<{tag}(?:\s+[^>]*?)?>([\s\S]*?)</{tag}>"
            match = re.search(closed_pattern, text, re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                return LLMResponseParser.extract_code_block(content)

            # 2b. Try unclosed tag (common in truncated outputs)
            unclosed_pattern = rf"<{tag}(?:\s+[^>]*?)?>([\s\S]*)$"
            match = re.search(unclosed_pattern, text, re.IGNORECASE)
            if match:
                content = match.group(1).strip()
                return LLMResponseParser.extract_code_block(content)

        # 3. Try language-aware markdown extraction if path provided
        if file_path:
            content = LLMResponseParser.extract_code_block_for_file(text, file_path)
            if content != text.strip():
                return content

        # 4. Try generic markdown extraction
        content = LLMResponseParser.extract_code_block(text)
        if content != text.strip():
            return content

        # 5. Fallback: return stripped text but clean artifacts
        return LLMResponseParser.clean_markdown_artifacts(text)

    @staticmethod
    def clean_markdown_artifacts(text: str) -> str:
        """
        Aggressively removes markdown fences and other common LLM artifacts (like XML tags).
        Useful when the LLM wraps code in markdown or tags despite instructions.
        """
        if not text:
            return ""

        # Remove markdown fences
        text = re.sub(r"```(?:\w+)?\n?", "", text)
        text = text.replace("```", "")

        # Remove common XML tags that might leak
        tags_to_strip = ["code_created", "file_content", "code_fixed", "repaired_code", "reflection", "thought"]
        for tag in tags_to_strip:
            text = re.sub(rf"</?{tag}(?:\s+[^>]*?)?>", "", text, flags=re.IGNORECASE)

        return text.strip()
