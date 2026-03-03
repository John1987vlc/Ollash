import pytest
from unittest.mock import MagicMock
from backend.utils.domains.auto_generation.improvement_suggester import ImprovementSuggester


@pytest.fixture
def mock_deps():
    return {"llm_client": MagicMock(), "logger": MagicMock(), "response_parser": MagicMock()}


@pytest.fixture
def suggester(mock_deps):
    return ImprovementSuggester(**mock_deps)


@pytest.mark.unit
async def test_suggest_improvements(suggester, mock_deps):
    mock_deps["llm_client"].chat.return_value = ({"message": {"content": "- suggestion 1\n- suggestion 2"}}, {})

    suggestions = await suggester.suggest_improvements("desc", "readme", {}, {}, 1)

    assert suggestions == ["suggestion 1", "suggestion 2"]
    mock_deps["llm_client"].chat.assert_called()


@pytest.mark.unit
class TestImprovementSuggesterRiskBased:
    """E4: Risk-based security-priority improvement suggestions."""

    @pytest.fixture
    def llm_client(self):
        client = MagicMock()
        client.chat.return_value = (
            {"message": {"content": "- Fix SQL injection\n- Add input validation\n"}},
            {},
        )
        return client

    @pytest.fixture
    def mock_vulnerability_scanner(self):
        from backend.utils.core.analysis.vulnerability_scanner import ProjectScanReport, ScanResult

        scanner = MagicMock()
        report = MagicMock(spec=ProjectScanReport)
        report.total_vulnerabilities = 3
        report.critical_count = 2
        report.high_count = 1
        report.blocked_files = ["src/auth.py"]
        result = MagicMock(spec=ScanResult)
        result.file_path = "src/auth.py"
        result.max_severity = "CRITICAL"
        result.vulnerabilities = [MagicMock(), MagicMock()]
        report.file_results = [result]
        scanner.scan_project.return_value = report
        return scanner

    def _get_user_message(self, llm_client):
        call_args = llm_client.chat.call_args
        messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
        return next(m["content"] for m in messages if m["role"] == "user")

    async def test_with_scanner_injects_security_priority(self, llm_client, mock_vulnerability_scanner):
        suggester = ImprovementSuggester(
            llm_client=llm_client,
            logger=MagicMock(),
            response_parser=MagicMock(),
            vulnerability_scanner=mock_vulnerability_scanner,
        )
        await suggester.suggest_improvements("A web app", "# README", {}, {"app.py": "x=1"}, 0)

        user_content = self._get_user_message(llm_client)
        assert "SECURITY PRIORITY" in user_content

    async def test_without_scanner_backward_compatible(self, llm_client):
        suggester = ImprovementSuggester(
            llm_client=llm_client,
            logger=MagicMock(),
            response_parser=MagicMock(),
            vulnerability_scanner=None,
        )
        result = await suggester.suggest_improvements("A web app", "# README", {}, {"app.py": "x=1"}, 0)

        assert isinstance(result, list)
        user_content = self._get_user_message(llm_client)
        assert "SECURITY PRIORITY" not in user_content

    async def test_no_security_block_when_zero_vulns(self, llm_client):
        scanner = MagicMock()
        report = MagicMock()
        report.total_vulnerabilities = 0
        report.critical_count = 0
        report.high_count = 0
        report.file_results = []
        scanner.scan_project.return_value = report

        suggester = ImprovementSuggester(
            llm_client=llm_client,
            logger=MagicMock(),
            response_parser=MagicMock(),
            vulnerability_scanner=scanner,
        )
        await suggester.suggest_improvements("A web app", "# README", {}, {"app.py": "x=1"}, 0)

        user_content = self._get_user_message(llm_client)
        assert "SECURITY PRIORITY" not in user_content

    async def test_scanner_exception_does_not_crash(self, llm_client):
        scanner = MagicMock()
        scanner.scan_project.side_effect = RuntimeError("Scanner unavailable")

        suggester = ImprovementSuggester(
            llm_client=llm_client,
            logger=MagicMock(),
            response_parser=MagicMock(),
            vulnerability_scanner=scanner,
        )
        result = await suggester.suggest_improvements("A web app", "# README", {}, {"app.py": "x=1"}, 0)
        assert isinstance(result, list)
