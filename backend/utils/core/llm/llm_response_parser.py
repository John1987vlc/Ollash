from typing import Dict, List, Tuple
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
        # This is common in smaller models or specific instructions.
        # Non-greedy .*? for arguments, handling both closed and unclosed brackets.
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
                # Try a very loose JSON extraction if direct load fails
                try:
                    # Fix unescaped backslashes before space or end of string common in paths C:\
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

        # Format 3: Raw JSON object that looks like a tool call if it is the only thing in the block
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
    def remove_think_blocks(response):
        if not response:
            return "", ""
        # Match both <thinking_process> and <proceso_de_pensamiento> to be safe with smaller models
        match = re.search(
            r"<(?:think|thinking_process|proceso_de_pensamiento)>([\s\S]*?)(?:</(?:think|thinking_process|proceso_de_pensamiento)>|$)",
            response,
            re.I,
        )
        if not match:
            return response, ""
        return re.sub(
            r"<(?:think|thinking_process|proceso_de_pensamiento)>[\s\S]*?(?:</(?:think|thinking_process|proceso_de_pensamiento)>|$)",
            "",
            response,
            flags=re.I,
        ).strip(), match.group(1).strip()

    @staticmethod
    def extract_raw_content(response):
        if not response:
            return ""

        # 1. Clean thinking blocks first
        cleaned, _ = LLMResponseParser.remove_think_blocks(response)
        if not cleaned.strip():
            return ""

        # 2. Try to extract from specific code-wrapping tags (case-insensitive)
        tag_match = re.search(
            r"<(?:code_created|plan_json|backlog_json|structure_json|contingency_json)>([\s\S]*?)(?:</(?:code_created|plan_json|backlog_json|structure_json|contingency_json)>|$)",
            cleaned,
            re.I,
        )

        if tag_match:
            # If tags are present, ONLY take what's inside
            content = tag_match.group(1).strip()
            # If there's a markdown block inside the tags, extract it
            if "```" in content:
                return LLMResponseParser.extract_single_code_block(content)
            return content

        # 3. If no tags, fall back to standard extraction
        if "```" in cleaned:
            return LLMResponseParser.extract_single_code_block(cleaned)

        return cleaned.strip()

    @staticmethod
    def extract_single_code_block(response):
        cleaned, _ = LLMResponseParser.remove_think_blocks(response)
        # More robust regex: \n? after opening, \n? before closing
        match = re.search(r"```(?:\w+)?\s*\n?([\s\S]*?)\n?\s*```", cleaned)
        if match:
            return match.group(1).strip()
        cleaned = cleaned.strip()
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
    def extract_json(response):
        if not response:
            return None

        # 1. Intentar extraer de tags específicos (case-insensitive)
        tag_match = re.search(
            r"<(?:plan_json|backlog_json|code_created|senior_review_json|tool_call|structure_json|contingency_json)>([\s\S]*?)(?:</(?:plan_json|backlog_json|code_created|senior_review_json|tool_call|structure_json|contingency_json)>|$)",
            response,
            re.I,
        )

        content_to_parse = response
        if tag_match:
            content_to_parse = tag_match.group(1).strip()
            # Limpiar posibles bloques de código dentro de los tags
            content_to_parse = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", content_to_parse, flags=re.M).strip()

        # 2. Limpieza estándar (remover bloques de pensamiento)
        cleaned, _ = LLMResponseParser.remove_think_blocks(content_to_parse)

        # Limpieza de bloques de código si no se usaron tags
        if not tag_match:
            cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", cleaned.strip(), flags=re.M).strip()

        # 3. Reparación agresiva de caracteres y formato
        repaired = LLMResponseParser._repair_json_string(cleaned)

        # 4. Multi-attempt parsing
        result = None

        # Attempt A: Direct parse
        try:
            result = json.loads(repaired)
        except:
            # Attempt B: Heuristic search for { } or [ ]
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
        # Si el resultado es un dict con una sola clave interesante, o una envoltura conocida, devolver el interior
        if isinstance(result, dict):
            # Claves de envoltura comunes que los modelos suelen añadir
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
                    # Si es la única clave, o si las otras claves son metadatos pequeños (strings/ints)
                    other_keys = [k for k in result.keys() if k != key]
                    if not other_keys or all(not isinstance(result[k], (list, dict)) for k in other_keys):
                        return result[key]

            # Si el dict es muy pequeño (1-2 claves) y una de ellas es una lista, devolver la lista
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

        # 1. Basic cleanup of encoding artifacts and smart quotes
        s = s.replace("â€\u009d", '"').replace("â€œ", '"').replace("â€™", "'").replace("â€˜", "'")
        s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")

        # 2. Remove comments (MUST do this before fixing newlines)
        s = re.sub(r"//.*$", "", s, flags=re.M)
        s = re.sub(r"/\*[\s\S]*?\*/", "", s)

        # 3. Fix literal newlines inside strings
        def fix_newlines(match):
            return match.group(0).replace("\n", "\\n").replace("\r", "")

        s = re.sub(r'"[\s\S]*?"', fix_newlines, s)

        # 4. Fix hallucinated notes in parentheses inside arrays or after values
        # e.g., ["path" (note)] -> ["path"] or {"key": "val" (note)} -> {"key": "val"}
        s = re.sub(r'("[\s\S]*?")\s*\([\s\S]*?\)', r"\1", s)

        # 5. Remove trailing commas before closing braces/brackets
        s = re.sub(r",\s*([\]}])", r"\1", s)

        # 6. Fix unescaped backslashes (common in Windows paths)
        # Only fix if not already part of an escape sequence
        s = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", s)

        # 7. Final pass: ensure we don't have control characters that break JSON
        # Replace literal tabs with spaces, etc.
        s = s.replace("\t", "    ")

        return s.strip()

    @staticmethod
    def extract_thought_action(response: str) -> Tuple[str, str]:
        """Extract (thought, action) from an LLM response supporting two formats.

        Format 1 — JSON object:
            {"thought": "...", "action": "..."}

        Format 2 — XML-style tags:
            <thought>...</thought><action>...</action>

        If neither format matches, returns ("", cleaned_response) so the caller
        can still use the full response as the action.

        This method is ADDITIVE and does NOT replace any existing parsing method.

        Args:
            response: Raw LLM response string.

        Returns:
            Tuple of (thought_str, action_str). Both may be empty strings.
        """
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
    def extract_multiple_files(response):
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
                        files[name] = "\n".join(content).strip()
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
            files[name] = "\n".join(content).strip()
        return files
