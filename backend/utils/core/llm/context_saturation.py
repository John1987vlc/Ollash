"""Context saturation utility.

Estimates whether a prompt is approaching the model's context window limit
and returns a warning string when the threshold is exceeded.
"""

from __future__ import annotations

import re
from typing import Optional

# Maps parameter-count suffix → approximate context window in tokens.
_MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "3b": 4096,
    "4b": 4096,
    "7b": 8192,
    "8b": 8192,
    "13b": 16384,
    "14b": 16384,
    "30b": 32768,
    "34b": 32768,
    "70b": 65536,
}
_DEFAULT_CONTEXT_WINDOW = 8192
_SATURATION_THRESHOLD = 0.6
_CHARS_PER_TOKEN = 1.3  # Conservative word-to-token multiplier


def _infer_context_window(model_name: str) -> int:
    """Return the approximate context window for *model_name*."""
    match = re.search(r"(\d+(?:\.\d+)?)b", model_name.lower())
    if not match:
        return _DEFAULT_CONTEXT_WINDOW
    param_count = float(match.group(1))
    # Find the smallest key whose param count >= param_count
    for key in sorted(_MODEL_CONTEXT_WINDOWS, key=lambda k: float(k[:-1])):
        if param_count <= float(key[:-1]):
            return _MODEL_CONTEXT_WINDOWS[key]
    # Larger than all known sizes — use the biggest window
    return max(_MODEL_CONTEXT_WINDOWS.values())


def check_context_saturation(prompt: str, model_name: str) -> Optional[str]:
    """Check whether *prompt* approaches the model context window.

    Uses ``word_count × 1.3`` as a conservative token estimate.

    Args:
        prompt: Full prompt text about to be sent to the LLM.
        model_name: Ollama model identifier (e.g. ``"qwen3-coder:30b"``).

    Returns:
        A warning string such as
        ``"Context saturation: 78% of qwen3-coder:30b's 32768-token window used."``
        when saturation exceeds 60 %, or ``None`` otherwise.
    """
    if not prompt:
        return None

    context_window = _infer_context_window(model_name)
    estimated_tokens = len(prompt.split()) * _CHARS_PER_TOKEN
    saturation = estimated_tokens / context_window

    if saturation > _SATURATION_THRESHOLD:
        pct = int(saturation * 100)
        return (
            f"Context saturation: {pct}% of {model_name}'s "
            f"{context_window}-token window estimated in use."
        )
    return None
