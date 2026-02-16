"""Tests for Heartbeat."""

from backend.utils.core.heartbeat import Heartbeat


class TestHeartbeat:
    def test_heartbeat_start_stop(self):
        hb = Heartbeat("test-model", "test-task", interval=60)
        hb.start()
        hb.stop()
        # No assertion needed - just verify no crash

    def test_heartbeat_with_logger(self):
        class FakeLogger:
            def __init__(self):
                self.messages = []

            def info(self, msg):
                self.messages.append(msg)

        logger = FakeLogger()
        hb = Heartbeat("model", "task", interval=60, logger=logger)
        hb.start()
        hb.stop()
        # Logger should not have been called since interval > test duration
