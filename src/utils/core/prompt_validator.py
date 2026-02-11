"""Validate prompt JSON files against the expected schema.

Each prompt file must be a JSON object with at least:
- "name" (str): Human-readable agent name
- "prompt" (str, non-empty): The system prompt text
"""

import json
from pathlib import Path
from typing import List, Tuple


# Required top-level keys and their expected types
_REQUIRED_FIELDS = {
    "name": str,
    "prompt": str,
}


def validate_prompt_file(path: Path) -> Tuple[bool, List[str]]:
    """Validate a single prompt JSON file.

    Returns:
        (is_valid, list_of_error_messages)
    """
    errors: List[str] = []

    if not path.exists():
        return False, [f"File not found: {path}"]

    if path.suffix != ".json":
        return False, [f"Expected .json file, got: {path.suffix}"]

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]

    if not isinstance(data, dict):
        return False, [f"Expected JSON object, got {type(data).__name__}"]

    for field, expected_type in _REQUIRED_FIELDS.items():
        if field not in data:
            errors.append(f"Missing required field: '{field}'")
        elif not isinstance(data[field], expected_type):
            errors.append(
                f"Field '{field}' must be {expected_type.__name__}, "
                f"got {type(data[field]).__name__}"
            )
        elif expected_type is str and not data[field].strip():
            errors.append(f"Field '{field}' must not be empty")

    return len(errors) == 0, errors


def validate_all_prompts(prompts_dir: Path) -> Tuple[bool, dict]:
    """Validate all prompt JSON files under the given directory.

    Returns:
        (all_valid, {relative_path: [errors]} for files with errors)
    """
    results = {}
    all_valid = True

    for prompt_file in sorted(prompts_dir.rglob("*.json")):
        is_valid, errors = validate_prompt_file(prompt_file)
        if not is_valid:
            rel_path = str(prompt_file.relative_to(prompts_dir))
            results[rel_path] = errors
            all_valid = False

    return all_valid, results
