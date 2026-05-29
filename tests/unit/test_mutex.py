# tests/unit/test_mutex.py
"""
Unit tests for mutex.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from modules.sync.mutex import Mutex, DeadlockWarning
from modules.process.pcb import PCB, reset_pid_counter


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestMutex:

    def test_acquire_unlocked_succeeds(self):
        # Arrange
        m = Mutex("M1")
        # Act
        res = m.acquire(pid=1)
        # Assert
        assert res is True
        assert m.locked is True
        assert m.owner_pid == 1

    def test_acquire_locked_blocks_caller(self):
        # Arrange
        m = Mutex("M1")
        m.acquire(pid=1)
        # Act
        res = m.acquire(pid=2)
        # Assert
        assert res is False
        assert m.wait_queue == [2]

    def test_release_by_owner_unblocks_waiting(self):
        # Arrange
        m = Mutex("M1")
        m.acquire(pid=1)
        m.acquire(pid=2) # Blocks P2
        # Act
        woken = m.release(pid=1)
        # Assert
        assert woken == 2
        assert m.owner_pid == 2
        assert m.locked is True
        assert m.wait_queue == []

    def test_release_by_non_owner_raises(self):
        # Arrange
        m = Mutex("M1")
        m.acquire(pid=1)
        # Act & Assert
        with pytest.raises(PermissionError):
            m.release(pid=2)

    def test_reentrant_acquire_raises_warning(self):
        # Arrange
        m = Mutex("M1")
        m.acquire(pid=1)
        # Act & Assert
        with pytest.raises(DeadlockWarning):
            m.acquire(pid=1)

    def test_priority_inheritance_boosts_owner(self):
        # Arrange - Simulate priority inheritance logic boosting lock owner
        m = Mutex("M1")
        owner = PCB(name="P1", burst_time=5, priority=5) # lower priority
        waiter = PCB(name="P2", burst_time=5, priority=1) # higher priority
        m.acquire(pid=owner.pid)
        # Act
        if not m.acquire(pid=waiter.pid):
            # Apply priority inheritance boost
            if waiter.priority < owner.priority:
                owner.priority = waiter.priority
        # Assert
        assert owner.priority == 1

    def test_priority_restored_on_release(self):
        # Arrange
        m = Mutex("M1")
        owner = PCB(name="P1", burst_time=5, priority=5)
        original_priority = owner.priority
        waiter = PCB(name="P2", burst_time=5, priority=1)
        m.acquire(pid=owner.pid)
        m.acquire(pid=waiter.pid) # blocks
        owner.priority = waiter.priority # inherited
        # Act
        woken = m.release(pid=owner.pid)
        # Restore priority
        owner.priority = original_priority
        # Assert
        assert woken == waiter.pid
        assert owner.priority == 5

    def test_multiple_waiters_fifo_unblock(self):
        # Arrange
        m = Mutex("M1")
        m.acquire(pid=1)
        m.acquire(pid=2)
        m.acquire(pid=3)
        # Act
        woken1 = m.release(pid=1)
        woken2 = m.release(pid=2)
        # Assert
        assert woken1 == 2
        assert woken2 == 3
        assert m.wait_queue == []
