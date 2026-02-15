import json
import re
from pathlib import Path
from typing import Dict, List, Optional


class LLMResponseParser:
    """Parses LLM responses: code block extraction, JSON extraction, raw content cleanup."""

    @staticmethod
    def extract_raw_content(response: str) -> str:
        """Primary method: extracts raw file content from an LLM response.

        If the response contains markdown fences, strips them.
        If it doesn't, returns the content as-is (trimmed).
        """
        stripped = response.strip()
        if not stripped:
            return ""

        # Check if the whole response is wrapped in a single code block
        if stripped.startswith("```"):
            return LLMResponseParser.extract_single_code_block(stripped)

        return stripped

    @staticmethod
    def extract_single_code_block(response: str) -> str:
        """Extracts content from a single markdown code block.

        Falls back to stripping leading/trailing ``` markers.
        """
        code_block_match = re.search(r"```(?:\w+)?\n([\s\S]*?)\n```", response)
        if code_block_match:
            return code_block_match.group(1).strip()

        # Fallback: strip markers manually
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if len(lines) > 0:
                cleaned = "\n".join(lines[1:])

        if cleaned.endswith("```"):
            lines = cleaned.splitlines()
            if len(lines) > 0 and lines[-1].strip() == "```":
                cleaned = "\n".join(lines[:-1])

        return cleaned.strip()

    @staticmethod
    def extract_json(response: str) -> Optional[dict]:
        """Extracts JSON from an LLM response with multiple fallback strategies.

        Returns the parsed dict or None if all strategies fail.
        """
        stripped = response.strip()

        # Strategy 1: direct parse
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        # Strategy 2: extract from code block
        code_content = LLMResponseParser.extract_single_code_block(stripped)
        try:
            return json.loads(code_content)
        except json.JSONDecodeError:
            pass

        # Strategy 3: find first { to last }
        if "{" in code_content:
            json_str = code_content[code_content.index("{") :]
            if "}" in json_str:
                json_str = json_str[: json_str.rindex("}") + 1]
                # Try fixing common issues
                json_str = LLMResponseParser.fix_incomplete_json(json_str)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

        return None

    @staticmethod
    def fix_incomplete_json(json_str: str) -> str:
        """Fixes common issues with incomplete JSON from LLM responses."""
        # Use a stack to track nesting order so closers are appended correctly
        stack = []
        in_string = False
        escape_next = False
        for ch in json_str:
            if escape_next:
                escape_next = False
                continue
            if ch == "\\":
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                stack.append("}")
            elif ch == "[":
                stack.append("]")
            elif ch in ("}", "]"):
                if stack and stack[-1] == ch:
                    stack.pop()

        # Append missing closers in reverse nesting order
        if stack:
            json_str += "".join(reversed(stack))

        # Remove trailing commas before closing braces/brackets
        json_str = re.sub(r",(\s*[}\]])", r"\1", json_str)

        return json_str

    @staticmethod
    def extract_multiple_files(response: str) -> Dict[str, str]:
        """Parses a response containing multiple files with filename markers.

        Supports formats:
          # filename: path/to/file
          ```lang
          ... code ...
          ```

          // filename: path/to/file
          ```lang
          ... code ...
          ```

        Returns {relative_path: content} dict.
        """
        files = {}
        lines = response.splitlines()
        current_file_content: List[str] = []
        current_filename: Optional[str] = None
        in_code_block = False
        potential_filename: Optional[str] = None

        for line in lines:
            stripped = line.strip()

            # Look for filename directive outside code blocks
            if not in_code_block:
                filename_match = re.search(
                    r"(?:#|//)[\s]*filename:\s*([^\n]+)", stripped
                )
                if filename_match:
                    raw = filename_match.group(1).strip()
                    potential_filename = (
                        Path(raw).as_posix().replace("..", "").lstrip("/")
                    )
                    continue

            if stripped.startswith("```"):
                if in_code_block:
                    # End of block
                    if current_filename:
                        files[current_filename] = "\n".join(
                            current_file_content
                        ).strip()
                    current_file_content = []
                    current_filename = None
                    in_code_block = False
                    potential_filename = None
                else:
                    # Start of block
                    in_code_block = True
                    if potential_filename:
                        current_filename = potential_filename
                        potential_filename = None
                    elif "# filename:" in line:
                        raw = line.split("# filename:", 1)[1].strip()
                        current_filename = (
                            Path(raw).as_posix().replace("..", "").lstrip("/")
                        )
                    else:
                        current_filename = None
            elif in_code_block:
                # Check for filename directive inside the code block
                if current_filename is None and stripped.startswith(
                    ("# filename:", "// filename:")
                ):
                    raw = stripped.split(":", 1)[1].strip()
                    current_filename = (
                        Path(raw).as_posix().replace("..", "").lstrip("/")
                    )
                else:
                    current_file_content.append(line)

        # Handle unclosed final block
        if in_code_block and current_filename:
            files[current_filename] = "\n".join(current_file_content).strip()

        return files
