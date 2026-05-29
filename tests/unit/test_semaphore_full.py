# tests/unit/test_semaphore_full.py
"""Tests for full semaphore coverage — BinarySemaphore.signal success path."""
from modules.sync.semaphore import BinarySemaphore


class TestBinarySemaphoreSignal:
    def test_binary_signal_after_wait_succeeds(self):
        bs = BinarySemaphore()
        bs.wait(pid=1)  # value goes to 0
        result = bs.signal(pid=1)
        assert result is None
        assert bs.value == 1

    def test_binary_signal_wakes_waiter(self):
        bs = BinarySemaphore()
        bs.wait(pid=1)  # value 0
        bs.wait(pid=2)  # value -1, pid 2 blocked
        woken = bs.signal(pid=1)
        assert woken == 2
