# tests/scenarios/test_deadlock_scenario.py
"""
Scenario tests for deadlock detection and recovery.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import DeadlockConfig
from core.event_bus import EventBus
from modules.sync.deadlock import DeadlockDetector
from modules.process.pcb import reset_pid_counter


@pytest.fixture(autouse=True)
def reset_pids():
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestDeadlockScenario:

    def test_dining_philosophers_deadlock(self):
        """Classic 5-philosopher deadlock: all hold left fork, request right fork."""
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())

        # Each philosopher holds their left fork
        for i in range(5):
            detector.update("allocate", pid=i, resource_id=f"F{i}")

        # Each philosopher requests their right fork
        for i in range(5):
            detector.update("request", pid=i, resource_id=f"F{(i+1) % 5}")

        cycles = detector.detect()
        assert len(cycles) > 0
        cycle_pids = set(pid for c in cycles for pid in c)
        assert set(range(5)).issubset(cycle_pids)

    def test_dining_philosophers_recovery(self):
        """Recovery via terminate_youngest breaks dining philosophers deadlock."""
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())

        for i in range(5):
            detector.update("allocate", pid=i, resource_id=f"F{i}")
        for i in range(5):
            detector.update("request", pid=i, resource_id=f"F{(i+1) % 5}")

        cycles = detector.detect()
        assert len(cycles) > 0

        affected = detector.recover(cycles, strategy="terminate_youngest")
        assert len(affected) >= 1

        # After recovery, no more deadlock
        cycles_after = detector.detect()
        assert cycles_after == []

    def test_bankers_algorithm_textbook_safe(self):
        """Section 18.5 Banker's Algorithm — safe state verification."""
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())

        available = {"A": 3, "B": 3, "C": 2}
        allocation = {
            0: {"A": 0, "B": 1, "C": 0},
            1: {"A": 2, "B": 0, "C": 0},
            2: {"A": 3, "B": 0, "C": 2},
            3: {"A": 2, "B": 1, "C": 1},
            4: {"A": 0, "B": 0, "C": 2},
        }
        need = {
            0: {"A": 7, "B": 4, "C": 3},
            1: {"A": 1, "B": 2, "C": 2},
            2: {"A": 6, "B": 0, "C": 0},
            3: {"A": 0, "B": 1, "C": 1},
            4: {"A": 4, "B": 3, "C": 1},
        }

        assert detector.is_safe_state(available, allocation, need) is True

    def test_two_process_deadlock_detection_and_recovery(self):
        """Canonical 2-process deadlock: P1 holds R1 requests R2, P2 holds R2 requests R1."""
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())

        detector.update("allocate", pid=1, resource_id="R1")
        detector.update("allocate", pid=2, resource_id="R2")
        detector.update("request", pid=1, resource_id="R2")
        detector.update("request", pid=2, resource_id="R1")

        cycles = detector.detect()
        assert len(cycles) > 0
        cycle_pids = set(pid for c in cycles for pid in c)
        assert 1 in cycle_pids and 2 in cycle_pids

        # Recover
        affected = detector.recover(cycles, strategy="resource_preempt")
        assert len(affected) == 1

        # Verify recovery
        cycles_after = detector.detect()
        assert cycles_after == []

    def test_no_deadlock_with_linear_wait(self):
        """Linear resource chain (no cycle) should not be detected as deadlock."""
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())

        detector.update("allocate", pid=1, resource_id="R1")
        detector.update("allocate", pid=2, resource_id="R2")
        detector.update("request", pid=2, resource_id="R1")
        # P1 does NOT request R2 → no cycle

        cycles = detector.detect()
        assert cycles == []
