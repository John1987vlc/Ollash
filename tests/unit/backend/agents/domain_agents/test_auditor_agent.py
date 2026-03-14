"""Unit tests for AuditorAgent."""

import pytest
from unittest.mock import MagicMock
from backend.agents.domain_agents.auditor_agent import AuditorAgent
from backend.agents.orchestrators.task_dag import AgentType, TaskNode


@pytest.fixture
def mock_scan_result_clean():
    sr = MagicMock()
    sr.vulnerabilities = []
    return sr


@pytest.fixture
def mock_scan_result_critical():
    vuln = MagicMock()
    vuln.severity = "critical"
    sr = MagicMock()
    sr.vulnerabilities = [vuln]
    return sr


@pytest.fixture
def mock_vuln_scanner(mock_scan_result_clean):
    vs = MagicMock()
    vs.scan_file.return_value = mock_scan_result_clean
    return vs


@pytest.fixture
def auditor(mock_vuln_scanner):
    ep = MagicMock()
    ep.subscribe = MagicMock()
    ep.publish_sync = MagicMock()
    return AuditorAgent(
        vulnerability_scanner=mock_vuln_scanner,
        code_quarantine=MagicMock(),
        event_publisher=ep,
        logger=MagicMock(),
        tool_dispatcher=MagicMock(),
    )


def _make_bb():
    bb = MagicMock()
    bb.write_sync = MagicMock()
    return bb


@pytest.mark.unit
class TestAuditorAgent:
    def test_subscribes_to_file_generated_on_init(self, auditor):
        auditor._event_publisher.subscribe.assert_called_with("file_generated", auditor._on_file_generated)

    def test_audit_file_writes_scan_result(self, auditor, mock_scan_result_clean):
        bb = _make_bb()
        auditor.set_blackboard(bb)
        auditor._audit_file("src/main.py", "def main(): pass")
        bb.write_sync.assert_called_once()
        written_key = bb.write_sync.call_args.args[0]
        assert "scan_results/src/main.py" in written_key

    def test_audit_file_clean_publishes_audit_completed(self, auditor):
        bb = _make_bb()
        auditor.set_blackboard(bb)
        auditor._audit_file("src/main.py", "x = 1")
        event_calls = [c.args[0] for c in auditor._event_publisher.publish_sync.call_args_list]
        assert "audit_completed" in event_calls

    def test_audit_file_critical_quarantines(self, auditor, mock_vuln_scanner, mock_scan_result_critical):
        mock_vuln_scanner.scan_file.return_value = mock_scan_result_critical
        bb = _make_bb()
        auditor.set_blackboard(bb)
        auditor._audit_file("src/dangerous.py", "import os; os.system('rm -rf /')")
        auditor._quarantine.quarantine_file.assert_called_once()

    def test_audit_file_critical_publishes_critical_event(self, auditor, mock_vuln_scanner, mock_scan_result_critical):
        mock_vuln_scanner.scan_file.return_value = mock_scan_result_critical
        bb = _make_bb()
        auditor.set_blackboard(bb)
        auditor._audit_file("src/evil.py", "import os")
        event_calls = [c.args[0] for c in auditor._event_publisher.publish_sync.call_args_list]
        assert "audit_critical_found" in event_calls

    def test_run_batch_scans_all_files(self, auditor):
        bb = _make_bb()
        bb.read.return_value = None
        bb.get_all_generated_files.return_value = {
            "src/a.py": "a = 1",
            "src/b.py": "b = 2",
        }
        auditor.set_blackboard(bb)
        node = TaskNode(id="__auditor_final__", agent_type=AgentType.AUDITOR, task_data={})
        result = auditor.run(node, bb)
        assert result["total_files"] == 2
        assert result["newly_scanned"] == 2
