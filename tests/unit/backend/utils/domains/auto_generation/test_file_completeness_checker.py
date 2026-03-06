import pytest
from unittest.mock import MagicMock, AsyncMock
from backend.utils.domains.auto_generation.file_completeness_checker import FileCompletenessChecker
from backend.utils.core.analysis.file_validator import ValidationStatus, ValidationResult


@pytest.fixture
def mock_llm_client():
    client = MagicMock()
    client.achat = AsyncMock()
    return client


@pytest.fixture
def mock_logger():
    return MagicMock()


@pytest.fixture
def mock_parser():
    parser = MagicMock()
    parser.extract_code.side_effect = lambda x, p=None: x  # Simplest passthrough
    return parser


@pytest.fixture
def mock_validator():
    validator = MagicMock()
    return validator


@pytest.fixture
def checker(mock_llm_client, mock_logger, mock_parser, mock_validator):
    return FileCompletenessChecker(
        llm_client=mock_llm_client,
        logger=mock_logger,
        response_parser=mock_parser,
        file_validator=mock_validator,
        max_retries_per_file=2,
    )


@pytest.mark.asyncio
async def test_verify_and_fix_all_valid(checker, mock_validator):
    files = {"main.py": "print('hello')"}
    mock_validator.validate_batch.return_value = [ValidationResult("main.py", ValidationStatus.VALID, "OK", 1, 14)]

    result = await checker.verify_and_fix(files)
    assert result == files
    assert checker.llm_client.achat.call_count == 0


@pytest.mark.asyncio
async def test_verify_and_fix_empty_file_triggers_generation(checker, mock_llm_client, mock_validator, mock_parser):
    files = {"empty.py": ""}
    # 1. First validation says it's empty
    # 2. After "generation", second validation says it's valid
    mock_validator.validate_batch.return_value = [ValidationResult("empty.py", ValidationStatus.EMPTY, "Empty", 0, 0)]
    mock_validator.validate.return_value = ValidationResult("empty.py", ValidationStatus.VALID, "OK", 3, 30)

    mock_llm_client.achat.return_value = ({"message": {"content": "print('generated')"}}, {})
    mock_parser.extract_code.return_value = "print('generated')"

    result = await checker.verify_and_fix(files, "readme context")

    assert result["empty.py"] == "print('generated')"
    assert mock_llm_client.achat.call_count == 1


@pytest.mark.asyncio
async def test_verify_and_fix_failed_file_triggers_fix(checker, mock_llm_client, mock_validator, mock_parser):
    files = {"buggy.py": "def f():"}
    mock_validator.validate_batch.return_value = [
        ValidationResult("buggy.py", ValidationStatus.SYNTAX_ERROR, "Invalid syntax", 1, 8)
    ]
    mock_validator.validate.return_value = ValidationResult("buggy.py", ValidationStatus.VALID, "Fixed", 2, 15)

    mock_llm_client.achat.return_value = ({"message": {"content": "def f():\n    pass"}}, {})
    mock_parser.extract_code.return_value = "def f():\n    pass"

    result = await checker.verify_and_fix(files)

    assert "pass" in result["buggy.py"]
    assert mock_llm_client.achat.call_count == 1


@pytest.mark.asyncio
async def test_verify_and_fix_max_retries_reached(checker, mock_llm_client, mock_validator, mock_parser):
    files = {"stubborn.py": "error"}
    mock_validator.validate_batch.return_value = [
        ValidationResult("stubborn.py", ValidationStatus.SYNTAX_ERROR, "Error", 1, 5)
    ]
    # Always returns error
    mock_validator.validate.return_value = ValidationResult(
        "stubborn.py", ValidationStatus.SYNTAX_ERROR, "Still error", 1, 5
    )

    mock_llm_client.achat.return_value = ({"message": {"content": "attempt"}}, {})

    result = await checker.verify_and_fix(files)

    # Content should be what we had (or last attempt depending on implementation,
    # but here it was 'error' originally and we 'gave up')
    assert result["stubborn.py"] == "attempt"  # It stores the last attempt even if it failed
    assert mock_llm_client.achat.call_count == 2  # max_retries_per_file is 2 in fixture
