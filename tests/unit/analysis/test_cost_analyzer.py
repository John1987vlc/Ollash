import pytest
import json
from unittest.mock import MagicMock
from backend.utils.core.analysis.cost_analyzer import CostAnalyzer

def test_cost_analyzer_report_generation():
    """Verifica que el generador de informes de coste calcule correctamente los tokens."""
    mock_logger = MagicMock()
    # Mock para evitar que intente leer de una DB real en el init
    mock_logger.structured_logger.db.fetch_all.return_value = []
    
    analyzer = CostAnalyzer(logger=mock_logger)
    analyzer.record_usage(model_name="qwen3", phase_name="test", prompt_tokens=100, completion_tokens=50)
    
    report = analyzer.get_report()
    assert report.total_tokens == 150
    assert report.total_requests == 1
    assert "qwen3" in report.usage_by_model

def test_cost_analyzer_historical_load_mapping():
    """Verifica que el mapeo de registros desde la base de datos sea correcto."""
    mock_logger = MagicMock()
    fake_db_row = {
        "extra_data": json.dumps({
            "type": "llm_response",
            "model": "gpt-oss",
            "usage": {"prompt_tokens": 10, "completion_tokens": 20}
        }),
        "timestamp": "2026-02-23 20:00:00"
    }
    mock_logger.structured_logger.db.fetch_all.return_value = [fake_db_row]
    
    analyzer = CostAnalyzer(logger=mock_logger)
    assert len(analyzer._records) == 1
    assert analyzer._records[0].model_name == "gpt-oss"
    assert analyzer._records[0].total_tokens == 30
