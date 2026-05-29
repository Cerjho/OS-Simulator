# tests/integration/test_sync_scenarios.py
"""
Integration tests for synchronization scenarios.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import DeadlockConfig
from core.event_bus import EventBus
from modules.sync.mutex import Mutex
from modules.sync.semaphore import Semaphore
from modules.sync.deadlock import DeadlockDetector
from modules.process.pcb import reset_pid_counter


@pytest.fixture(autouse=True)
def reset_pids():
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestSyncScenarios:

    def test_mutex_and_deadlock_detector_integration(self):
        """Mutex acquire/release events are tracked by DeadlockDetector."""
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())
        m1 = Mutex("R1")
        m2 = Mutex("R2")

        # P1 acquires R1
        m1.acquire(pid=1)
        detector.update("allocate", pid=1, resource_id="R1")

        # P2 acquires R2
        m2.acquire(pid=2)
        detector.update("allocate", pid=2, resource_id="R2")

        # P1 requests R2 (blocked)
        m1.try_acquire(pid=2)  # P2 tries R1 — but that's m1
        detector.update("request", pid=1, resource_id="R2")
        detector.update("request", pid=2, resource_id="R1")

        cycles = detector.detect()
        assert len(cycles) > 0

    def test_semaphore_producer_consumer_bounded_buffer(self):
        """Producer-consumer bounded buffer simulation using semaphores."""
        empty = Semaphore(initial_value=3)  # buffer capacity
        full = Semaphore(initial_value=0)
        mutex = Mutex("buffer_lock")
        buffer = []

        # Producer produces 3 items
        for i in range(3):
            assert empty.wait(pid=100) is True  # decrement empty
            mutex.acquire(pid=100)
            buffer.append(f"item_{i}")
            mutex.release(pid=100)
            full.signal(pid=100)

        assert len(buffer) == 3
        assert full.value == 3

        # Consumer consumes 3 items
        consumed = []
        for i in range(3):
            assert full.wait(pid=200) is True
            mutex.acquire(pid=200)
            consumed.append(buffer.pop(0))
            mutex.release(pid=200)
            empty.signal(pid=200)

        assert len(consumed) == 3
        assert len(buffer) == 0
        assert empty.value == 3

    def test_deadlock_detection_and_recovery_cycle(self):
        """Full cycle: detect deadlock → recover → verify clean state."""
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())

        # Create circular wait
        detector.update("allocate", pid=1, resource_id="R1")
        detector.update("allocate", pid=2, resource_id="R2")
        detector.update("allocate", pid=3, resource_id="R3")
        detector.update("request", pid=1, resource_id="R2")
        detector.update("request", pid=2, resource_id="R3")
        detector.update("request", pid=3, resource_id="R1")

        cycles = detector.detect()
        assert len(cycles) > 0

        # Recover
        affected = detector.recover(cycles, strategy="terminate_youngest")
        assert len(affected) >= 1

        # After recovery, should be no deadlock
        cycles_after = detector.detect()
        assert cycles_after == []

    def test_multiple_mutexes_no_deadlock(self):
        """Processes acquiring in the same order do not deadlock."""
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())

        # Both P1 and P2 acquire R1 first, then R2 — no circular wait
        detector.update("allocate", pid=1, resource_id="R1")
        detector.update("request", pid=2, resource_id="R1")  # P2 waits for R1

        cycles = detector.detect()
        assert cycles == []

    def test_semaphore_blocks_correctly_when_exhausted(self):
        """Counting semaphore blocks after exhausting all permits."""
        sem = Semaphore(initial_value=2)
        assert sem.wait(pid=1) is True   # value=1
        assert sem.wait(pid=2) is True   # value=0
        assert sem.wait(pid=3) is False  # value=-1, blocked
        assert sem.wait_queue == [3]

        woken = sem.signal(pid=1)
        assert woken == 3
        assert sem.wait_queue == []
