import json
import re
from pathlib import Path
from typing import Dict, List, Optional


class LLMResponseParser:
    """Parses LLM responses: code block extraction, JSON extraction, raw content cleanup."""

    @staticmethod
    def remove_think_blocks(response: str) -> tuple[str, str]:
        """Removes reasoning blocks wrapped in <think> or <thinking_process> tags.
        
        Returns a tuple: (cleaned_response, think_content).
        Supports unclosed blocks by assuming the rest of the text is reasoning.
        """
        if not response:
            return "", ""

        # Check for both <think> and <thinking_process>
        # re.DOTALL is crucial to match across newlines
        think_match = re.search(r"<(?:think|thinking_process)>([\s\S]*?)(?:</(?:think|thinking_process)>|$)", response, re.IGNORECASE)
        
        if not think_match:
            return response, ""
        
        think_content = think_match.group(1).strip()
        # Remove the block.
        cleaned_response = re.sub(r"<(?:think|thinking_process)>[\s\S]*?(?:</(?:think|thinking_process)>|$)", "", response, flags=re.IGNORECASE).strip()
        
        return cleaned_response, think_content

    @staticmethod
    def extract_raw_content(response: str) -> str:
        """Primary method: extracts raw file content from an LLM response.

        If the response contains markdown fences, strips them.
        If it doesn't, returns the content as-is (trimmed).
        """
        # Step 1: Standardize by removing reasoning blocks
        cleaned_response, _ = LLMResponseParser.remove_think_blocks(response)
        
        stripped = cleaned_response.strip()
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
        # Step 1: Standardize by removing reasoning blocks
        cleaned_response, _ = LLMResponseParser.remove_think_blocks(response)
        
        code_block_match = re.search(r"```(?:\w+)?\n([\s\S]*?)\n```", cleaned_response)
        if code_block_match:
            return code_block_match.group(1).strip()

        # Fallback: strip markers manually
        cleaned = cleaned_response.strip()
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
    def extract_json(response: str) -> Optional[dict | list]:
        """Extracts JSON from an LLM response with specialized XML tag support and fallback strategies."""
        if not response:
            return None

        # Strategy 0: Look for specialized tags first (highest precision)
        # We search for <plan_json>, <backlog_json>, <code_created>, <senior_review_json> etc.
        tag_pattern = re.compile(r"<(?:plan_json|backlog_json|code_created|senior_review_json)>([\s\S]*?)(?:</(?:plan_json|backlog_json|code_created|senior_review_json)>|$)", re.IGNORECASE)
        tag_match = tag_pattern.search(response)
        if tag_match:
            content = tag_match.group(1).strip()
            # Clean potential markdown from inside tags
            content = re.sub(r"^```(?:json)?\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
            try:
                return json.loads(content.strip())
            except json.JSONDecodeError:
                # If direct parse fails, proceed to general extraction on the tag content
                response = content

        # Step 1: Standardize by removing reasoning blocks
        cleaned_response, _ = LLMResponseParser.remove_think_blocks(response)
        
        # Step 2: Clean potential markdown markers from the start/end
        stripped = cleaned_response.strip()
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
        stripped = stripped.strip()

        # Strategy 1: Direct parse
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Find the FIRST '[' or '{' and LAST ']' or '}'
        # This is more robust against leading/trailing text like markdown blocks or comments
        # We search from the end for the last closer to handle trailing noise
        first_bracket = stripped.find('[')
        first_brace = stripped.find('{')
        
        start_idx = -1
        if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
            start_idx = first_bracket
            closer = ']'
        elif first_brace != -1:
            start_idx = first_brace
            closer = '}'
            
        if start_idx != -1:
            last_idx = stripped.rfind(closer)
            if last_idx > start_idx:
                json_str = stripped[start_idx:last_idx + 1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    # Try fixing common issues
                    fixed = LLMResponseParser.fix_incomplete_json(json_str)
                    try:
                        return json.loads(fixed)
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
        # Step 1: Standardize by removing reasoning blocks
        cleaned_response, _ = LLMResponseParser.remove_think_blocks(response)
        
        files = {}
        lines = cleaned_response.splitlines()
        current_file_content: List[str] = []
        current_filename: Optional[str] = None
        in_code_block = False
        potential_filename: Optional[str] = None

        for line in lines:
            stripped = line.strip()

            # Look for filename directive outside code blocks
            if not in_code_block:
                filename_match = re.search(r"(?:#|//)[\s]*filename:\s*([^\n]+)", stripped)
                if filename_match:
                    raw = filename_match.group(1).strip()
                    potential_filename = Path(raw).as_posix().replace("..", "").lstrip("/")
                    continue

            if stripped.startswith("```"):
                if in_code_block:
                    # End of block
                    if current_filename:
                        files[current_filename] = "\n".join(current_file_content).strip()
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
                        current_filename = Path(raw).as_posix().replace("..", "").lstrip("/")
                    else:
                        current_filename = None
            elif in_code_block:
                # Check for filename directive inside the code block
                if current_filename is None and stripped.startswith(("# filename:", "// filename:")):
                    raw = stripped.split(":", 1)[1].strip()
                    current_filename = Path(raw).as_posix().replace("..", "").lstrip("/")
                else:
                    current_file_content.append(line)

        # Handle unclosed final block
        if in_code_block and current_filename:
            files[current_filename] = "\n".join(current_file_content).strip()

        return files
