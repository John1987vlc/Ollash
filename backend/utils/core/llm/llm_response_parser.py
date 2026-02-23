import json
import re
from pathlib import Path


class LLMResponseParser:
    @staticmethod
    def remove_think_blocks(response):
        if not response:
            return "", ""
        match = re.search(r"<(?:think|thinking_process)>([\s\S]*?)(?:</(?:think|thinking_process)>|$)", response, re.I)
        if not match:
            return response, ""
        return re.sub(
            r"<(?:think|thinking_process)>[\s\S]*?(?:</(?:think|thinking_process)>|$)", "", response, flags=re.I
        ).strip(), match.group(1).strip()

    @staticmethod
    def extract_raw_content(response):
        cleaned, _ = LLMResponseParser.remove_think_blocks(response)
        if not cleaned.strip():
            return ""
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
            r"<(?:plan_json|backlog_json|code_created|senior_review_json)>([\s\S]*?)(?:</(?:plan_json|backlog_json|code_created|senior_review_json)>|$)",
            response,
            re.I,
        )
        if tag_match:
            content = tag_match.group(1).strip()
            # Limpiar posibles bloques de código dentro de los tags
            content = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", content, flags=re.M).strip()
            try:
                return json.loads(content)
            except:
                # Si falla el parseo directo, intentamos la búsqueda heurística dentro del contenido del tag
                response = content

        # 2. Limpieza estándar (remover bloques de pensamiento)
        cleaned, _ = LLMResponseParser.remove_think_blocks(response)

        # 3. Limpiar bloques de código Markdown
        stripped = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", cleaned.strip(), flags=re.M).strip()

        # 4. Intento de carga directa
        try:
            return json.loads(stripped)
        except:
            pass

        # 5. Búsqueda heurística de estructura JSON (el primer { o [ hasta el último } o ])
        # Esto rescata JSONs enterrados en texto explicativo
        fb = stripped.find("[")
        fbr = stripped.find("{")

        if fb != -1 and (fbr == -1 or fb < fbr):
            start, closer = fb, "]"
        elif fbr != -1:
            start, closer = fbr, "}"
        else:
            return None

        last = stripped.rfind(closer)
        if last > start:
            candidate = stripped[start : last + 1]
            try:
                # Limpieza agresiva de comentarios estilo JS que a veces los modelos meten
                candidate_clean = re.sub(r"//.*$", "", candidate, flags=re.M)
                return json.loads(candidate_clean)
            except:
                # Último intento: intentar corregir comas finales (trailing commas) que rompen el JSON estándar
                try:
                    candidate_no_trailing = re.sub(r",\s*([\]}])", r"\1", candidate_clean)
                    return json.loads(candidate_no_trailing)
                except:
                    pass
        return None

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
