"""Tests for NetworkMonitor — ring buffer, whitelist, summary."""

import pytest

from backend.utils.core.system.network_monitor import NetworkMonitor

pytestmark = pytest.mark.unit


@pytest.fixture
def monitor():
    """Fresh NetworkMonitor with default localhost whitelist."""
    m = NetworkMonitor()
    m.clear()
    return m


class TestRecord:
    def test_record_localhost_is_local(self, monitor):
        monitor.record("http://localhost:11434/api/chat", "POST", 200)
        log = monitor.get_log()
        assert len(log) == 1
        assert log[0]["is_external"] is False

    def test_record_127_0_0_1_is_local(self, monitor):
        monitor.record("http://127.0.0.1:11434/api/chat", "POST", 200)
        assert monitor.get_log()[0]["is_external"] is False

    def test_record_external_host_is_external(self, monitor):
        monitor.record("https://api.openai.com/v1/chat", "POST", 200)
        assert monitor.get_log()[0]["is_external"] is True

    def test_record_captures_url_method_status(self, monitor):
        monitor.record("http://localhost:11434/api/embed", "POST", 201)
        entry = monitor.get_log()[0]
        assert entry["url"] == "http://localhost:11434/api/embed"
        assert entry["method"] == "POST"
        assert entry["status_code"] == 201

    def test_record_never_raises(self, monitor):
        """record() must be bulletproof — bad URL should not raise."""
        monitor.record("not_a_url", "??", -1)  # should not raise

    def test_record_timestamps_are_floats(self, monitor):
        monitor.record("http://localhost:11434/", "GET", 200)
        assert isinstance(monitor.get_log()[0]["ts"], float)


class TestGetLog:
    def test_get_log_empty(self, monitor):
        assert monitor.get_log() == []

    def test_get_log_newest_first(self, monitor):
        monitor.record("http://localhost:11434/a", "GET", 200)
        monitor.record("http://localhost:11434/b", "GET", 200)
        log = monitor.get_log()
        assert log[0]["url"].endswith("/b")
        assert log[1]["url"].endswith("/a")

    def test_get_log_respects_limit(self, monitor):
        for i in range(10):
            monitor.record(f"http://localhost/{i}", "GET", 200)
        assert len(monitor.get_log(limit=3)) == 3

    def test_ring_buffer_max_size(self):
        m = NetworkMonitor()
        m.clear()
        for i in range(600):
            m.record(f"http://localhost/{i}", "GET", 200)
        assert len(m.get_log(limit=1000)) == 500  # capped at _MAX_ENTRIES


class TestSummary:
    def test_summary_empty(self, monitor):
        s = monitor.summary()
        assert s["total_calls"] == 0
        assert s["local_calls"] == 0
        assert s["external_calls"] == 0
        assert s["is_clean"] is True

    def test_summary_counts_correctly(self, monitor):
        monitor.record("http://localhost:11434/", "GET", 200)
        monitor.record("http://localhost:11434/", "POST", 200)
        monitor.record("https://evil.example.com/", "POST", 200)
        s = monitor.summary()
        assert s["total_calls"] == 3
        assert s["local_calls"] == 2
        assert s["external_calls"] == 1
        assert s["is_clean"] is False

    def test_summary_is_clean_when_only_local(self, monitor):
        monitor.record("http://localhost:11434/api/chat", "POST", 200)
        assert monitor.summary()["is_clean"] is True

    def test_summary_external_urls_listed(self, monitor):
        monitor.record("https://telemetry.vendor.io/track", "POST", 200)
        s = monitor.summary()
        assert "https://telemetry.vendor.io/track" in s["external_urls"]

    def test_summary_allowed_hosts(self, monitor):
        hosts = monitor.summary()["allowed_hosts"]
        assert "localhost" in hosts


class TestClear:
    def test_clear_empties_log(self, monitor):
        monitor.record("http://localhost:11434/", "GET", 200)
        assert len(monitor.get_log()) == 1
        monitor.clear()
        assert len(monitor.get_log()) == 0

    def test_clear_resets_summary(self, monitor):
        monitor.record("https://external.com/", "GET", 200)
        monitor.clear()
        assert monitor.summary()["total_calls"] == 0
        assert monitor.summary()["is_clean"] is True


class TestAllowedHosts:
    def test_add_allowed_host(self, monitor):
        monitor.add_allowed_host("192.168.1.100")
        monitor.record("http://192.168.1.100:11434/api/chat", "POST", 200)
        assert monitor.get_log()[0]["is_external"] is False

    def test_get_allowed_hosts_returns_list(self, monitor):
        hosts = monitor.get_allowed_hosts()
        assert isinstance(hosts, list)
        assert "localhost" in hosts
