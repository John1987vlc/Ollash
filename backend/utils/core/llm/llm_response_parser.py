from typing import Dict, List, Tuple, Optional, Any
import json
import re
import time
from pathlib import Path


class LLMResponseParser:
    @staticmethod
    def parse_tool_calls(text: str) -> List[Dict]:
        """Extracts tool calls from text in multiple formats (JSON tags, [TOOL_CALL] markers, etc)."""
        if not text:
            return []

        tool_calls = []

        # Format 1: [TOOL_CALL: name{"arg": "val"}] or [TOOL_CALL: name(args)]
        matches = re.finditer(r"\[TOOL_CALL:\s*(\w+)\s*(\{.*?\})(?:\]|$)", text, re.S)
        for i, m in enumerate(matches):
            name = m.group(1)
            raw_args = m.group(2)
            try:
                args = json.loads(raw_args)
                tool_calls.append(
                    {
                        "id": f"extracted_{i}_{int(time.time())}",
                        "type": "function",
                        "function": {"name": name, "arguments": args},
                    }
                )
            except:
                try:
                    fixed_args = re.sub(r"\\(\s|$)", r"\\\\\1", raw_args)
                    args = json.loads(fixed_args)
                    tool_calls.append(
                        {
                            "id": f"extracted_fixed_{i}_{int(time.time())}",
                            "type": "function",
                            "function": {"name": name, "arguments": args},
                        }
                    )
                except:
                    continue

        # Format 2: <tool_call>JSON</tool_call>
        tags = re.finditer(r"<tool_call>(.*?)</tool_call>", text, re.S | re.I)
        for i, m in enumerate(tags):
            try:
                data = json.loads(m.group(1).strip())
                if isinstance(data, dict):
                    tool_calls.append(
                        {
                            "id": f"tag_{i}_{int(time.time())}",
                            "type": "function",
                            "function": {"name": data.get("name"), "arguments": data.get("arguments", {})},
                        }
                    )
            except:
                continue

        # Format 3: Raw JSON object
        if not tool_calls:
            potential_json = LLMResponseParser.extract_json(text)
            if (
                isinstance(potential_json, dict)
                and "name" in potential_json
                and ("arguments" in potential_json or "args" in potential_json)
            ):
                tool_calls.append(
                    {
                        "id": f"json_{int(time.time())}",
                        "type": "function",
                        "function": {
                            "name": potential_json.get("name"),
                            "arguments": potential_json.get("arguments") or potential_json.get("args") or {},
                        },
                    }
                )

        return tool_calls

    @staticmethod
    def remove_think_blocks(response: str) -> Tuple[str, str]:
        """Removes <think> blocks and returns (cleaned_text, extracted_thought)."""
        if not response:
            return "", ""
        match = re.search(
            r"<(?:think|thinking_process|proceso_de_pensamiento)>([\s\S]*?)(?:</(?:think|thinking_process|proceso_de_pensamiento)>|$)",
            response,
            re.I,
        )
        if not match:
            return response, ""
        cleaned = re.sub(
            r"<(?:think|thinking_process|proceso_de_pensamiento)>[\s\S]*?(?:</(?:think|thinking_process|proceso_de_pensamiento)>|$)",
            "",
            response,
            flags=re.I,
        ).strip()
        return cleaned, match.group(1).strip()

    @staticmethod
    def extract_raw_content(response: str) -> str:
        """
        Extracts the main content from an LLM response, handling tags and markdown.
        Designed to be extremely robust against nested wrappers and conversational noise.
        """
        if not response:
            return ""

        # 1. Clean thinking blocks first
        cleaned, _ = LLMResponseParser.remove_think_blocks(response)
        if not cleaned.strip():
            return ""

        # 2. Use the aggressive iterative extractor
        return LLMResponseParser.extract_single_code_block(cleaned)

    @staticmethod
    def extract_single_code_block(text: str) -> str:
        """
        Aggressively strips markdown markers and XML-style tags from text.
        Iteratively removes wrappers until no more wrapping artifacts are detected.
        """
        if not text:
            return ""

        current = text.strip()
        tag_names = [
            "code_created",
            "plan_json",
            "backlog_json",
            "structure_json",
            "contingency_json",
            "review_json",
            "senior_review_json",
        ]

        # Iterative cleaning to handle nested wrappers (e.g. <tag>```js\ncode\n```</tag>)
        for _ in range(5):
            old = current

            # A. XML Tags wrapping the whole thing
            tag_pattern = r"^<(" + "|".join(tag_names) + r")[^>]*>([\s\S]*?)(?:</\1>|$)"
            tag_match = re.search(tag_pattern, current, re.I | re.S)
            if tag_match:
                current = tag_match.group(2).strip()
                if current != old:
                    continue

            # B. Markdown blocks wrapping the whole thing
            # Strict wrapping from ^ to $
            md_wrap_match = re.search(r"^```(?:\w+)?\s*\n?([\s\S]*?)\n?\s*```$", current, re.S)
            if md_wrap_match:
                current = md_wrap_match.group(1).strip()
                # Remove lang ID if it's the only thing on the first line
                lines = current.splitlines()
                if lines and not lines[0].strip().startswith("```"):
                    if re.match(r"^[a-zA-Z0-9+#-]+$", lines[0].strip()):
                        current = "\n".join(lines[1:]).strip()
                if current != old:
                    continue

            # C. Conversational text + block fallback
            # If not perfectly wrapped, try to find the FIRST discrete block
            if "```" in current:
                blocks = re.findall(r"```(?:\w+)?\s*\n?([\s\S]*?)\n?\s*```", current, re.S)
                if blocks:
                    # Take the first non-empty block
                    non_empty = [b.strip() for b in blocks if b.strip()]
                    if non_empty:
                        # Recursive call to strip any wrappers inside this block
                        candidate = non_empty[0]
                        # Only take it if it was clearly meant to be a block (surrounded by conversational text)
                        # or if it's our only option.
                        if len(blocks) == 1:
                            # Heuristic: strip if there's conversational prefix
                            prefix = current[: current.find("```")].strip()
                            if prefix and not prefix.startswith(("#", "import", "from", "package", "name:")):
                                current = candidate
                                if current != old:
                                    continue

            break  # No more changes possible

        # D. Final surgical tag removal for unclosed tags at the very start/end
        lines = current.splitlines()
        if lines:
            if re.match(r"^<(" + "|".join(tag_names) + r")[^>]*>$", lines[0].strip(), re.I):
                lines = lines[1:]
            if lines and re.match(r"^</(" + "|".join(tag_names) + r")>$", lines[-1].strip(), re.I):
                lines = lines[:-1]
            current = "\n".join(lines).strip()

        return current

    @staticmethod
    def extract_code_block_for_file(text: str, file_path: str) -> str:
        """Language-aware code block extractor for a specific target file.

        When an LLM response contains multiple code blocks (common with verbose
        small models), this method prefers the block whose language hint matches
        the file extension rather than always taking the first block.

        Matching table (extension → accepted language hints in order of preference):

        =========  ================================
        Extension  Accepted hints
        =========  ================================
        .js/.mjs   ``javascript``, ``js``
        .jsx       ``jsx``, ``javascript``, ``js``
        .ts/.tsx   ``typescript``, ``ts``
        .html      ``html``
        .css       ``css``
        .py        ``python``, ``py``
        .go        ``go``
        .rs        ``rust``
        .json      ``json``
        .yaml      ``yaml``, ``yml``
        .md        ``markdown``, ``md``
        .sh        ``bash``, ``sh``, ``shell``
        .svg       ``svg``, ``xml``
        =========  ================================

        When no language-matched block is found, falls back to the *largest*
        non-empty block (which is more likely to be the actual implementation
        than a short illustrative snippet). Ultimate fallback is
        :meth:`extract_single_code_block`.

        Args:
            text: Raw LLM response (may contain ``<think>`` blocks, multiple
                markdown fences, XML tags, etc.).
            file_path: Relative or absolute path of the target file — only the
                extension is used.

        Returns:
            Extracted and cleaned code string, or ``""`` if nothing was found.
        """
        if not text:
            return ""

        # Strip thinking blocks before analysing
        cleaned, _ = LLMResponseParser.remove_think_blocks(text)

        _EXT_TO_LANGS: dict[str, list[str]] = {
            ".js": ["javascript", "js"],
            ".mjs": ["javascript", "js"],
            ".cjs": ["javascript", "js"],
            ".jsx": ["jsx", "javascript", "js"],
            ".ts": ["typescript", "ts"],
            ".tsx": ["tsx", "typescript", "ts"],
            ".html": ["html"],
            ".css": ["css"],
            ".scss": ["scss", "css"],
            ".py": ["python", "py"],
            ".go": ["go"],
            ".rs": ["rust"],
            ".java": ["java"],
            ".json": ["json"],
            ".yaml": ["yaml", "yml"],
            ".yml": ["yaml", "yml"],
            ".md": ["markdown", "md"],
            ".sh": ["bash", "sh", "shell"],
            ".bash": ["bash", "sh", "shell"],
            ".toml": ["toml"],
            ".xml": ["xml"],
            ".svg": ["svg", "xml"],
        }

        ext = Path(file_path).suffix.lower()
        lang_hints = _EXT_TO_LANGS.get(ext, [])

        # Collect all fenced code blocks: (language_hint, content)
        all_blocks = re.findall(r"```(\w*)\s*\n?([\s\S]*?)\n?\s*```", cleaned, re.S)

        if not all_blocks:
            # No fenced blocks — fall back to the standard extractor
            return LLMResponseParser.extract_single_code_block(cleaned)

        # Prefer the first block whose language hint matches the file extension
        if lang_hints:
            for hint, content in all_blocks:
                if hint.lower() in lang_hints and content.strip():
                    return content.strip()

        # No language match — take the largest non-empty block
        non_empty = [(h, c.strip()) for h, c in all_blocks if c.strip()]
        if non_empty:
            if len(non_empty) == 1:
                return non_empty[0][1]
            return max(non_empty, key=lambda x: len(x[1]))[1]

        # Ultimate fallback
        return LLMResponseParser.extract_single_code_block(cleaned)

    @staticmethod
    def extract_json(response: str) -> Optional[Any]:
        """Extracts and parses JSON from an LLM response with aggressive repair."""
        if not response:
            return None

        # 1. Standard cleaning
        cleaned, _ = LLMResponseParser.remove_think_blocks(response)

        # 2. Extract content using the aggressive logic
        json_text = LLMResponseParser.extract_single_code_block(cleaned)

        # 3. Aggressive character and format repair
        repaired = LLMResponseParser._repair_json_string(json_text)

        # 4. Multi-attempt parsing
        result = None
        try:
            result = json.loads(repaired)
        except:
            # Heuristic search for first [ or { and corresponding closer
            fb = repaired.find("[")
            fbr = repaired.find("{")

            if fb != -1 and (fbr == -1 or fb < fbr):
                start, closer = fb, "]"
            elif fbr != -1:
                start, closer = fbr, "}"
            else:
                return None

            last = repaired.rfind(closer)
            if last > start:
                candidate = repaired[start : last + 1]
                try:
                    result = json.loads(candidate)
                except:
                    pass

        # 5. SURGICAL EXTRACTION (The "flattening" logic)
        if isinstance(result, dict):
            wrappers = [
                "backlog",
                "tasks",
                "files",
                "folders",
                "plan",
                "architecture",
                "structure",
                "risks",
                "items",
                "logic_plan",
            ]
            for key in wrappers:
                if key in result and isinstance(result[key], (list, dict)):
                    other_keys = [k for k in result.keys() if k != key]
                    if not other_keys or all(not isinstance(result[k], (list, dict)) for k in other_keys):
                        return result[key]
            if len(result) <= 2:
                for val in result.values():
                    if isinstance(val, list) and len(val) > 0:
                        return val

        return result

    @staticmethod
    def _repair_json_string(s: str) -> str:
        """Applies multiple heuristics to fix common LLM JSON errors."""
        if not s:
            return s

        # Basic cleanup of encoding artifacts and smart quotes
        s = s.replace("â€\u009d", '"').replace("â€œ", '"').replace("â€™", "'").replace("â€˜", "'")
        s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")

        # Remove comments
        s = re.sub(r"//.*$", "", s, flags=re.M)
        s = re.sub(r"/\*[\s\S]*?\*/", "", s)

        # Fix literal newlines inside strings
        def fix_newlines(match):
            return match.group(0).replace("\n", "\\n").replace("\r", "")

        s = re.sub(r'"[\s\S]*?"', fix_newlines, s)

        # Fix hallucinated notes in parentheses after values
        s = re.sub(r'("[\s\S]*?")\s*\([\s\S]*?\)', r"\1", s)

        # Remove trailing commas
        s = re.sub(r",\s*([\]}])", r"\1", s)

        # Fix unescaped backslashes (common in Windows paths)
        s = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", s)

        # Final cleanup
        s = s.replace("\t", "    ")

        return s.strip()

    @staticmethod
    def extract_thought_action(response: str) -> Tuple[str, str]:
        """Extract (thought, action) from an LLM response."""
        if not response:
            return ("", "")

        cleaned, _ = LLMResponseParser.remove_think_blocks(response)

        # Format 1: JSON {"thought": "...", "action": "..."}
        json_candidate = LLMResponseParser.extract_json(cleaned)
        if isinstance(json_candidate, dict):
            thought = str(json_candidate.get("thought", ""))
            action = str(json_candidate.get("action", ""))
            if thought or action:
                return (thought, action)

        # Format 2: <thought>...</thought><action>...</action> tags
        thought_match = re.search(r"<thought>([\s\S]*?)</thought>", cleaned, re.I)
        action_match = re.search(r"<action>([\s\S]*?)</action>", cleaned, re.I)
        if thought_match or action_match:
            thought = thought_match.group(1).strip() if thought_match else ""
            action = action_match.group(1).strip() if action_match else ""
            return (thought, action)

        # Fallback: treat entire cleaned response as action
        return ("", cleaned.strip())

    @staticmethod
    def extract_multiple_files(response: str) -> Dict[str, str]:
        """Extracts multiple files from a single response using # filename: markers."""
        cleaned, _ = LLMResponseParser.remove_think_blocks(response)
        files = {}
        lines = cleaned.splitlines()
        content, name, in_block, pot_name = [], None, False, None

        for line in lines:
            stripped = line.strip()
            if not in_block:
                m = re.search(r"(?:#|//)[\s]*filename:\s*([^\n]+)", stripped)
                if m:
                    pot_name = Path(m.group(1).strip()).as_posix().replace("..", "").lstrip("/")
                    continue

            if stripped.startswith("```"):
                if in_block:
                    if name:
                        files[name] = LLMResponseParser.extract_single_code_block("\n".join(content))
                    content, name, in_block, pot_name = [], None, False, None
                else:
                    in_block = True
                    if pot_name:
                        name, pot_name = pot_name, None
                    elif "# filename:" in line:
                        name = Path(line.split("# filename:", 1)[1].strip()).as_posix().replace("..", "").lstrip("/")
            elif in_block:
                if name is None and stripped.startswith(("# filename:", "// filename:")):
                    name = Path(stripped.split(":", 1)[1].strip()).as_posix().replace("..", "").lstrip("/")
                else:
                    content.append(line)

        if in_block and name:
            files[name] = LLMResponseParser.extract_single_code_block("\n".join(content))

        return files
