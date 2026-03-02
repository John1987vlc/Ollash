"""Unit tests for phase_helpers.py."""

from unittest.mock import MagicMock, patch

import pytest

from backend.agents.auto_agent_phases.phase_helpers import (
    filter_structure_by_type,
    get_type_info_if_active,
)


def _make_type_info(project_type: str, confidence: float, extensions=None):
    info = MagicMock()
    info.project_type = project_type
    info.confidence = confidence
    info.allowed_extensions = frozenset(extensions or {".html", ".css", ".js"})
    return info


def _make_context(type_info=None):
    ctx = MagicMock()
    ctx.project_type_info = type_info
    return ctx


class TestGetTypeInfoIfActive:
    @pytest.mark.unit
    def test_returns_info_when_confident(self):
        info = _make_type_info("frontend_web", confidence=0.50)
        ctx = _make_context(info)
        result = get_type_info_if_active(ctx)
        assert result is info

    @pytest.mark.unit
    def test_returns_none_when_unknown_type(self):
        info = _make_type_info("unknown", confidence=0.80)
        ctx = _make_context(info)
        assert get_type_info_if_active(ctx) is None

    @pytest.mark.unit
    def test_returns_none_when_confidence_below_threshold(self):
        info = _make_type_info("python_app", confidence=0.05)
        ctx = _make_context(info)
        assert get_type_info_if_active(ctx) is None

    @pytest.mark.unit
    def test_returns_none_when_type_info_is_none(self):
        ctx = _make_context(None)
        assert get_type_info_if_active(ctx) is None

    @pytest.mark.unit
    def test_returns_none_when_attribute_missing(self):
        ctx = MagicMock(spec=[])  # No project_type_info attribute
        assert get_type_info_if_active(ctx) is None

    @pytest.mark.unit
    def test_returns_info_at_minimum_confidence(self):
        info = _make_type_info("go_service", confidence=0.10)
        ctx = _make_context(info)
        assert get_type_info_if_active(ctx) is info

    @pytest.mark.unit
    def test_returns_none_just_below_threshold(self):
        info = _make_type_info("go_service", confidence=0.09)
        ctx = _make_context(info)
        assert get_type_info_if_active(ctx) is None


class TestFilterStructureByType:
    @pytest.mark.unit
    def test_returns_original_when_no_type_info(self):
        ctx = _make_context(None)
        structure = {"path": "./", "files": ["main.py"], "folders": []}
        result = filter_structure_by_type(ctx, structure)
        assert result is structure

    @pytest.mark.unit
    def test_calls_filter_when_type_detected(self):
        info = _make_type_info("frontend_web", confidence=0.60, extensions=[".html", ".css"])
        ctx = _make_context(info)
        structure = {"path": "./", "files": ["index.html", "main.py"], "folders": []}

        with patch(
            "backend.utils.domains.auto_generation.structure_generator.StructureGenerator"
            ".filter_structure_by_extensions"
        ) as mock_filter:
            mock_filter.return_value = {"path": "./", "files": ["index.html"], "folders": []}
            result = filter_structure_by_type(ctx, structure)

        mock_filter.assert_called_once_with(structure, {".html", ".css"}, None)

    @pytest.mark.unit
    def test_passes_logger_through(self):
        info = _make_type_info("frontend_web", confidence=0.60)
        ctx = _make_context(info)
        logger = MagicMock()
        structure = {"path": "./", "files": [], "folders": []}

        with patch(
            "backend.utils.domains.auto_generation.structure_generator.StructureGenerator"
            ".filter_structure_by_extensions"
        ) as mock_filter:
            mock_filter.return_value = structure
            filter_structure_by_type(ctx, structure, logger=logger)

        _, _, passed_logger = mock_filter.call_args[0]
        assert passed_logger is logger
