"""Unit tests for context_saturation.py — Feature 6."""

import pytest

from backend.utils.core.llm.context_saturation import (
    _DEFAULT_CONTEXT_WINDOW,
    check_context_saturation,
    _infer_context_window,
)


@pytest.mark.unit
class TestInferContextWindow:
    def test_3b_model_returns_4096(self):
        assert _infer_context_window("ministral-3:3b") == 4096

    def test_7b_model_returns_8192(self):
        assert _infer_context_window("llama3:7b") == 8192

    def test_30b_model_returns_32768(self):
        assert _infer_context_window("qwen3-coder:30b") == 32768

    def test_unknown_model_returns_default(self):
        assert _infer_context_window("unknown-model") == _DEFAULT_CONTEXT_WINDOW

    def test_70b_model_returns_65536(self):
        assert _infer_context_window("llama3:70b") == 65536


@pytest.mark.unit
class TestCheckContextSaturation:
    def test_empty_prompt_returns_none(self):
        assert check_context_saturation("", "ministral-3:3b") is None

    def test_short_prompt_returns_none(self):
        # A few words will never hit 60% of 4096 tokens
        assert check_context_saturation("Hello world", "ministral-3:3b") is None

    def test_very_long_prompt_returns_warning(self):
        # 3000 words * 1.3 = 3900 tokens; 3900/4096 ≈ 95% > 60%
        long_prompt = " ".join(["word"] * 3000)
        result = check_context_saturation(long_prompt, "ministral-3:3b")
        assert result is not None
        assert "ministral-3:3b" in result
        assert "%" in result

    def test_warning_contains_model_name(self):
        long_prompt = " ".join(["word"] * 3000)
        result = check_context_saturation(long_prompt, "my-model:3b")
        assert "my-model:3b" in result

    def test_warning_contains_context_window_size(self):
        long_prompt = " ".join(["word"] * 3000)
        result = check_context_saturation(long_prompt, "ministral-3:3b")
        assert "4096" in result

    def test_large_model_tolerates_same_prompt(self):
        # 3000 words * 1.3 = 3900 tokens; 3900/65536 ≈ 6% < 60%
        long_prompt = " ".join(["word"] * 3000)
        assert check_context_saturation(long_prompt, "llama3:70b") is None

    def test_exact_threshold_boundary(self):
        # Just below threshold: should return None
        window = 4096
        # Need word_count * 1.3 <= 0.6 * 4096 = 2457.6 → word_count <= 1890
        below_prompt = " ".join(["word"] * 1800)
        assert check_context_saturation(below_prompt, "ministral-3:3b") is None
