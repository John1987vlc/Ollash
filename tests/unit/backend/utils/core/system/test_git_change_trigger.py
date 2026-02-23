"""Unit tests for GitChangeTrigger (E5)."""

import threading
import pytest
from unittest.mock import MagicMock, patch, call


@pytest.mark.unit
class TestGitChangeTrigger:
    """Tests for GitChangeTrigger daemon-thread polling logic."""

    @pytest.fixture
    def mock_logger(self):
        return MagicMock()

    @pytest.fixture
    def callback(self):
        return MagicMock()

    def _make_trigger(self, tmp_path, callback, mock_logger, poll_interval=30, min_lines=5):
        from backend.utils.core.system.git_change_trigger import GitChangeTrigger

        return GitChangeTrigger(
            repo_path=tmp_path,
            on_change_callback=callback,
            logger=mock_logger,
            poll_interval_seconds=poll_interval,
            min_changed_lines=min_lines,
        )

    # ------------------------------------------------------------------
    # Start / stop lifecycle
    # ------------------------------------------------------------------

    def test_start_sets_running_true(self, tmp_path, callback, mock_logger):
        trigger = self._make_trigger(tmp_path, callback, mock_logger)
        with patch("threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread
            trigger.start()
            assert trigger._running is True
            mock_thread.start.assert_called_once()

    def test_start_is_idempotent(self, tmp_path, callback, mock_logger):
        trigger = self._make_trigger(tmp_path, callback, mock_logger)
        with patch("threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread
            trigger.start()
            trigger.start()  # second call should be a no-op
            mock_thread_cls.assert_called_once()

    def test_stop_sets_running_false(self, tmp_path, callback, mock_logger):
        trigger = self._make_trigger(tmp_path, callback, mock_logger)
        trigger._running = True
        trigger.stop()
        assert trigger._running is False

    def test_stop_logs_message(self, tmp_path, callback, mock_logger):
        trigger = self._make_trigger(tmp_path, callback, mock_logger)
        trigger.stop()
        mock_logger.info.assert_called()

    # ------------------------------------------------------------------
    # Poll loop: callback fires when threshold exceeded
    # ------------------------------------------------------------------

    def test_callback_fires_when_total_exceeds_threshold(self, tmp_path, callback, mock_logger):
        """One poll iteration: total=20, last=0, threshold=5 → callback fires."""
        trigger = self._make_trigger(tmp_path, callback, mock_logger, min_lines=5)
        trigger._last_known_total = 0

        with patch.object(trigger.git, "diff_numstat", return_value={"success": True, "total": 20}):
            with patch("time.sleep", side_effect=StopIteration):
                trigger._running = True
                try:
                    trigger._poll_loop()
                except StopIteration:
                    pass

        callback.assert_called_once()
        assert trigger._last_known_total == 20

    def test_callback_does_not_fire_below_threshold(self, tmp_path, callback, mock_logger):
        """total=3, last=0, threshold=5 → callback must NOT fire."""
        trigger = self._make_trigger(tmp_path, callback, mock_logger, min_lines=5)
        trigger._last_known_total = 0

        with patch.object(trigger.git, "diff_numstat", return_value={"success": True, "total": 3}):
            with patch("time.sleep", side_effect=StopIteration):
                trigger._running = True
                try:
                    trigger._poll_loop()
                except StopIteration:
                    pass

        callback.assert_not_called()

    def test_callback_does_not_fire_when_total_unchanged(self, tmp_path, callback, mock_logger):
        """total=10, last=10, threshold=5 → delta=0 → no callback."""
        trigger = self._make_trigger(tmp_path, callback, mock_logger, min_lines=5)
        trigger._last_known_total = 10

        with patch.object(trigger.git, "diff_numstat", return_value={"success": True, "total": 10}):
            with patch("time.sleep", side_effect=StopIteration):
                trigger._running = True
                try:
                    trigger._poll_loop()
                except StopIteration:
                    pass

        callback.assert_not_called()

    def test_last_known_total_updated_after_callback(self, tmp_path, callback, mock_logger):
        trigger = self._make_trigger(tmp_path, callback, mock_logger, min_lines=5)
        trigger._last_known_total = 0

        with patch.object(trigger.git, "diff_numstat", return_value={"success": True, "total": 50}):
            with patch("time.sleep", side_effect=StopIteration):
                trigger._running = True
                try:
                    trigger._poll_loop()
                except StopIteration:
                    pass

        assert trigger._last_known_total == 50

    # ------------------------------------------------------------------
    # Error resilience
    # ------------------------------------------------------------------

    def test_poll_error_is_swallowed(self, tmp_path, callback, mock_logger):
        """A git exception must NOT crash the loop — swallowed and logged."""
        trigger = self._make_trigger(tmp_path, callback, mock_logger)

        with patch.object(trigger.git, "diff_numstat", side_effect=RuntimeError("git fail")):
            with patch("time.sleep", side_effect=StopIteration):
                trigger._running = True
                try:
                    trigger._poll_loop()
                except StopIteration:
                    pass

        callback.assert_not_called()
        mock_logger.warning.assert_called()

    def test_callback_exception_is_swallowed(self, tmp_path, mock_logger):
        """Callback raising an exception must NOT crash the loop."""
        bad_callback = MagicMock(side_effect=ValueError("callback boom"))
        trigger = self._make_trigger(tmp_path, bad_callback, mock_logger, min_lines=5)
        trigger._last_known_total = 0

        with patch.object(trigger.git, "diff_numstat", return_value={"success": True, "total": 20}):
            with patch("time.sleep", side_effect=StopIteration):
                trigger._running = True
                try:
                    trigger._poll_loop()
                except StopIteration:
                    pass

        mock_logger.error.assert_called()

    def test_failed_diff_numstat_does_not_fire_callback(self, tmp_path, callback, mock_logger):
        """success=False response → callback must not fire."""
        trigger = self._make_trigger(tmp_path, callback, mock_logger, min_lines=5)
        trigger._last_known_total = 0

        with patch.object(trigger.git, "diff_numstat", return_value={"success": False, "total": 100}):
            with patch("time.sleep", side_effect=StopIteration):
                trigger._running = True
                try:
                    trigger._poll_loop()
                except StopIteration:
                    pass

        callback.assert_not_called()

    # ------------------------------------------------------------------
    # Daemon thread attributes
    # ------------------------------------------------------------------

    def test_thread_is_daemon(self, tmp_path, callback, mock_logger):
        trigger = self._make_trigger(tmp_path, callback, mock_logger)
        captured = {}

        def mock_thread_constructor(**kwargs):
            captured.update(kwargs)
            t = MagicMock()
            return t

        with patch("threading.Thread", side_effect=mock_thread_constructor):
            trigger.start()

        assert captured.get("daemon") is True
        assert captured.get("name") == "GitChangeTrigger"
