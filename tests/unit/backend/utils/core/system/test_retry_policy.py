"""Unit tests for RetryPolicy (backend/utils/core/system/retry_policy.py)."""

import time
from unittest.mock import MagicMock, call

import pytest

from backend.utils.core.system.retry_policy import RetryPolicy


class TestRetryPolicySync:
    @pytest.mark.unit
    def test_succeeds_on_first_attempt(self):
        fn = MagicMock(return_value="ok")
        policy = RetryPolicy(max_attempts=3)
        result = policy.execute(fn, "arg1", kw="val")
        assert result == "ok"
        fn.assert_called_once_with("arg1", kw="val")

    @pytest.mark.unit
    def test_retries_on_exception_and_succeeds(self):
        fn = MagicMock(side_effect=[ValueError("first"), "ok"])
        policy = RetryPolicy(max_attempts=3, base_delay=0)
        result = policy.execute(fn)
        assert result == "ok"
        assert fn.call_count == 2

    @pytest.mark.unit
    def test_raises_after_max_attempts(self):
        fn = MagicMock(side_effect=RuntimeError("always fails"))
        policy = RetryPolicy(max_attempts=3, base_delay=0)
        with pytest.raises(RuntimeError, match="always fails"):
            policy.execute(fn)
        assert fn.call_count == 3

    @pytest.mark.unit
    def test_does_not_retry_unmatched_exception(self):
        fn = MagicMock(side_effect=KeyError("not retried"))
        policy = RetryPolicy(max_attempts=3, base_delay=0, exceptions=(ValueError,))
        with pytest.raises(KeyError):
            policy.execute(fn)
        assert fn.call_count == 1

    @pytest.mark.unit
    def test_max_attempts_one_means_no_retries(self):
        fn = MagicMock(side_effect=Exception("boom"))
        policy = RetryPolicy(max_attempts=1, base_delay=0)
        with pytest.raises(Exception):
            policy.execute(fn)
        assert fn.call_count == 1

    @pytest.mark.unit
    def test_delay_for_grows_exponentially(self):
        policy = RetryPolicy(base_delay=1.0, max_delay=100.0, backoff_factor=2.0)
        assert policy._delay_for(0) == 1.0
        assert policy._delay_for(1) == 2.0
        assert policy._delay_for(2) == 4.0
        assert policy._delay_for(3) == 8.0

    @pytest.mark.unit
    def test_delay_caps_at_max_delay(self):
        policy = RetryPolicy(base_delay=10.0, max_delay=15.0, backoff_factor=2.0)
        assert policy._delay_for(5) == 15.0

    @pytest.mark.unit
    def test_sleeps_between_retries(self, monkeypatch):
        sleep_calls = []
        monkeypatch.setattr(time, "sleep", lambda s: sleep_calls.append(s))
        fn = MagicMock(side_effect=[ValueError("a"), ValueError("b"), "ok"])
        policy = RetryPolicy(max_attempts=3, base_delay=1.0, backoff_factor=2.0, max_delay=100.0)
        result = policy.execute(fn)
        assert result == "ok"
        assert sleep_calls == [1.0, 2.0]

    @pytest.mark.unit
    def test_passes_args_and_kwargs_each_attempt(self):
        fn = MagicMock(side_effect=[Exception("fail"), "done"])
        policy = RetryPolicy(max_attempts=2, base_delay=0)
        policy.execute(fn, 1, 2, key="value")
        assert fn.call_args_list == [call(1, 2, key="value"), call(1, 2, key="value")]


class TestRetryPolicyAsyncRefactored:
    @pytest.mark.unit
    def test_async_succeeds_on_first_attempt_sync(self):
        def fn():
            return "async_ok"

        policy = RetryPolicy(max_attempts=3)
        assert policy.execute(fn) == "async_ok"

    @pytest.mark.unit
    def test_async_retries_on_exception_sync(self):
        call_count = 0

        def fn():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "success"

        policy = RetryPolicy(max_attempts=3, base_delay=0)
        result = policy.execute(fn)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.unit
    def test_async_raises_after_max_attempts_sync(self):
        def fn():
            raise RuntimeError("always fails")

        policy = RetryPolicy(max_attempts=2, base_delay=0)
        with pytest.raises(RuntimeError):
            policy.execute(fn)
