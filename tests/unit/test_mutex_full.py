# tests/unit/test_mutex_full.py
"""Tests for full mutex coverage — try_acquire paths."""
import pytest
from modules.sync.mutex import Mutex, DeadlockWarning


class TestTryAcquire:
    def test_try_acquire_success(self):
        m = Mutex("m1")
        assert m.try_acquire(pid=1) is True
        assert m.locked is True
        assert m.owner_pid == 1

    def test_try_acquire_fails_when_locked(self):
        m = Mutex("m1")
        m.acquire(pid=1)
        assert m.try_acquire(pid=2) is False

    def test_try_acquire_reentrant_raises(self):
        m = Mutex("m1")
        m.acquire(pid=1)
        with pytest.raises(DeadlockWarning):
            m.try_acquire(pid=1)
