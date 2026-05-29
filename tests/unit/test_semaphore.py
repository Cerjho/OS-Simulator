# tests/unit/test_semaphore.py
"""
Unit tests for semaphore.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from modules.sync.semaphore import Semaphore, BinarySemaphore
from modules.process.pcb import reset_pid_counter


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestSemaphore:

    def test_counting_semaphore_allows_multiple_acquires(self):
        # Arrange
        sem = Semaphore(initial_value=3)
        # Act & Assert
        assert sem.wait(pid=1) is True   # value=2
        assert sem.wait(pid=2) is True   # value=1
        assert sem.wait(pid=3) is True   # value=0

    def test_counting_semaphore_blocks_on_zero(self):
        # Arrange
        sem = Semaphore(initial_value=1)
        sem.wait(pid=1)  # value=0
        # Act
        res = sem.wait(pid=2)  # value=-1
        # Assert
        assert res is False
        assert sem.wait_queue == [2]

    def test_signal_wakes_blocked_process(self):
        # Arrange
        sem = Semaphore(initial_value=1)
        sem.wait(pid=1)   # value=0
        sem.wait(pid=2)   # value=-1, pid=2 blocks
        # Act
        woken = sem.signal(pid=1)
        # Assert
        assert woken == 2
        assert sem.wait_queue == []

    def test_signal_increments_value_when_no_waiters(self):
        # Arrange
        sem = Semaphore(initial_value=1)
        sem.wait(pid=1)   # value=0
        # Act
        woken = sem.signal(pid=1)
        # Assert
        assert woken is None
        assert sem.value == 1

    def test_negative_initial_value_raises(self):
        # Arrange & Act & Assert
        with pytest.raises(ValueError):
            Semaphore(initial_value=-1)

    def test_fifo_unblock_order(self):
        # Arrange
        sem = Semaphore(initial_value=0)
        sem.wait(pid=1)  # blocks
        sem.wait(pid=2)  # blocks
        sem.wait(pid=3)  # blocks
        # Act
        w1 = sem.signal(pid=99)
        w2 = sem.signal(pid=99)
        # Assert
        assert w1 == 1
        assert w2 == 2


class TestBinarySemaphore:

    def test_binary_initial_value_is_1(self):
        # Arrange & Act
        bs = BinarySemaphore()
        # Assert
        assert bs.value == 1

    def test_binary_signal_beyond_1_raises(self):
        # Arrange
        bs = BinarySemaphore()
        # Act & Assert — value is already 1, signaling exceeds ceiling
        with pytest.raises(ValueError):
            bs.signal(pid=1)
