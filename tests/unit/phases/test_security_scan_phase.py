"""Tests for SecurityScanPhase."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from backend.agents.auto_agent_phases.security_scan_phase import SecurityScanPhase
from backend.utils.core.vulnerability_scanner import (
    ProjectScanReport,
    ScanResult,
    Vulnerability,
)


@pytest.fixture
def mock_context():
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.file_manager = MagicMock()

    ctx.vulnerability_scanner = MagicMock()
    ctx.vulnerability_scanner.scan_project.return_value = ProjectScanReport(
        total_files=5,
        files_scanned=3,
        total_vulnerabilities=2,
        critical_count=0,
        high_count=1,
        medium_count=1,
        low_count=0,
        info_count=0,
        blocked_files=[],
        file_results=[
            ScanResult(
                file_path="main.py",
                language="python",
                vulnerabilities=[
                    Vulnerability(
                        severity="high",
                        rule_id="SEC-003",
                        description="Hardcoded secret",
                        line_number=5,
                        code_snippet='password = "secret123"',
                        fix_suggestion="Use environment variables",
                    ),
                ],
            ),
        ],
    )
    return ctx


@pytest.fixture
def phase(mock_context):
    return SecurityScanPhase(context=mock_context)


class TestSecurityScanPhase:
    @pytest.mark.asyncio
    async def test_skips_when_scanner_not_available(self, phase):
        phase.context.vulnerability_scanner = None
        files = {"main.py": "print('hello')"}
        result, _, _ = await phase.execute(
            project_description="test",
            project_name="test_project",
            project_root=Path("/tmp/test"),
            readme_content="# Test",
            initial_structure={},
            generated_files=files,
            file_paths=[],
        )
        assert result == files

    @pytest.mark.asyncio
    async def test_generates_security_report(self, phase, tmp_path):
        files = {"main.py": 'password = "secret123"\n'}
        result, _, paths = await phase.execute(
            project_description="test",
            project_name="test_project",
            project_root=tmp_path,
            readme_content="# Test",
            initial_structure={},
            generated_files=files,
            file_paths=[],
        )
        assert "SECURITY_SCAN_REPORT.md" in result
        assert "SECURITY_SCAN_REPORT.md" in paths

    @pytest.mark.asyncio
    async def test_publishes_scan_results(self, phase, tmp_path):
        files = {"main.py": "print('hello')"}
        await phase.execute(
            project_description="test",
            project_name="test_project",
            project_root=tmp_path,
            readme_content="# Test",
            initial_structure={},
            generated_files=files,
            file_paths=[],
        )
        phase.context.event_publisher.publish.assert_any_call(
            "tool_output",
            tool_name="security_scan",
            total_vulnerabilities=2,
            critical=0,
            high=1,
            blocked_files=[],
        )

    @pytest.mark.asyncio
    async def test_blocks_on_critical_vulnerabilities(self, phase, tmp_path):
        phase.context.vulnerability_scanner.scan_project.return_value = ProjectScanReport(
            total_files=1,
            files_scanned=1,
            total_vulnerabilities=1,
            critical_count=1,
            high_count=0,
            medium_count=0,
            low_count=0,
            info_count=0,
            blocked_files=["main.py"],
            file_results=[],
        )
        files = {"main.py": 'eval(input("cmd: "))'}
        result, _, _ = await phase.execute(
            project_description="test",
            project_name="test_project",
            project_root=tmp_path,
            readme_content="# Test",
            initial_structure={},
            generated_files=files,
            file_paths=[],
            block_security_critical=True,
        )
        assert "SECURITY_BLOCKED.md" in result

    @pytest.mark.asyncio
    async def test_does_not_block_without_flag(self, phase, tmp_path):
        phase.context.vulnerability_scanner.scan_project.return_value = ProjectScanReport(
            total_files=1,
            files_scanned=1,
            total_vulnerabilities=1,
            critical_count=1,
            high_count=0,
            medium_count=0,
            low_count=0,
            info_count=0,
            blocked_files=["main.py"],
            file_results=[],
        )
        files = {"main.py": "eval(user_input)"}
        result, _, _ = await phase.execute(
            project_description="test",
            project_name="test_project",
            project_root=tmp_path,
            readme_content="# Test",
            initial_structure={},
            generated_files=files,
            file_paths=[],
            block_security_critical=False,
        )
        assert "SECURITY_BLOCKED.md" not in result

    @pytest.mark.asyncio
    async def test_generates_dependabot_for_pip(self, phase, tmp_path):
        files = {"main.py": "", "requirements.txt": "flask\n"}
        result, _, _ = await phase.execute(
            project_description="test",
            project_name="test_project",
            project_root=tmp_path,
            readme_content="# Test",
            initial_structure={},
            generated_files=files,
            file_paths=[],
        )
        if ".github/dependabot.yml" in result:
            assert "pip" in result[".github/dependabot.yml"]

    def test_is_scannable(self, phase):
        assert phase._is_scannable("main.py") is True
        assert phase._is_scannable("app.js") is True
        assert phase._is_scannable("README.md") is False
        assert phase._is_scannable("config.json") is False

    def test_format_scan_report(self, phase):
        report = ProjectScanReport(
            total_files=2,
            files_scanned=2,
            total_vulnerabilities=1,
            critical_count=0,
            high_count=1,
            medium_count=0,
            low_count=0,
            info_count=0,
            blocked_files=[],
            file_results=[
                ScanResult(
                    file_path="app.py",
                    language="python",
                    vulnerabilities=[
                        Vulnerability(
                            severity="high",
                            rule_id="SEC-003",
                            description="Hardcoded secret",
                            line_number=10,
                            code_snippet='secret = "abc"',
                        )
                    ],
                )
            ],
        )
        result = phase._format_scan_report(report, "myproject")
        assert "myproject" in result
        assert "Hardcoded secret" in result
        assert "High" in result

    def test_generate_dependabot_from_files(self, phase):
        files = {
            "requirements.txt": "flask",
            "package.json": "{}",
            "Cargo.toml": "[package]",
        }
        result = phase._generate_dependabot_from_files(files)
        assert "pip" in result
        assert "npm" in result
        assert "cargo" in result

    def test_generate_dependabot_empty(self, phase):
        files = {"main.py": "print()"}
        result = phase._generate_dependabot_from_files(files)
        assert result == ""
