# tests/unit/test_deadlock.py
"""
Unit tests for deadlock.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import DeadlockConfig
from core.event_bus import EventBus
from modules.sync.deadlock import DeadlockDetector
from modules.process.pcb import reset_pid_counter


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestDeadlockDetector:

    def test_rag_detects_simple_cycle(self):
        # Arrange
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())
        detector.update("allocate", pid=1, resource_id="R1")
        detector.update("allocate", pid=2, resource_id="R2")
        # Act
        detector.update("request", pid=1, resource_id="R2")
        detector.update("request", pid=2, resource_id="R1")
        cycles = detector.detect()
        # Assert
        assert len(cycles) > 0
        cycle_pids = set(pid for c in cycles for pid in c)
        assert 1 in cycle_pids and 2 in cycle_pids

    def test_rag_no_cycle_returns_empty(self):
        # Arrange
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())
        detector.update("allocate", pid=1, resource_id="R1")
        # Act
        detector.update("request", pid=2, resource_id="R1")
        cycles = detector.detect()
        # Assert
        assert cycles == []

    def test_bankers_algorithm_safe_state(self):
        # Arrange - Section 18.5 values
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
        # Act
        safe = detector.is_safe_state(available, allocation, need)
        # Assert
        assert safe is True

    def test_bankers_algorithm_unsafe_state(self):
        # Arrange
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())
        available = {"A": 0, "B": 0, "C": 0}
        allocation = {0: {"A": 1}}
        need = {0: {"A": 2}}
        # Act
        safe = detector.is_safe_state(available, allocation, need)
        # Assert
        assert safe is False

    def test_recovery_terminates_youngest_process(self):
        # Arrange
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())
        detector.update("allocate", pid=1, resource_id="R1")
        detector.update("allocate", pid=2, resource_id="R2")
        detector.update("request", pid=1, resource_id="R2")
        detector.update("request", pid=2, resource_id="R1")
        cycles = detector.detect()
        # Act
        affected = detector.recover(cycles, strategy="terminate_youngest")
        # Assert
        assert affected == [2] # P2 has higher numerical PID = youngest

    def test_recovery_terminates_lowest_priority(self):
        # Arrange
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())
        detector.update("allocate", pid=1, resource_id="R1")
        detector.update("allocate", pid=2, resource_id="R2")
        detector.update("request", pid=1, resource_id="R2")
        detector.update("request", pid=2, resource_id="R1")
        cycles = detector.detect()
        # Act
        affected = detector.recover(cycles, strategy="terminate_lowest")
        # Assert
        assert len(affected) == 1

    def test_recovery_preempts_resource(self):
        # Arrange
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())
        detector.update("allocate", pid=1, resource_id="R1")
        detector.update("allocate", pid=2, resource_id="R2")
        detector.update("request", pid=1, resource_id="R2")
        detector.update("request", pid=2, resource_id="R1")
        cycles = detector.detect()
        # Act
        affected = detector.recover(cycles, strategy="resource_preempt")
        # Assert
        assert len(affected) == 1
        assert detector.detect() == [] # Cycle broken

    def test_update_allocations_tracks_resources(self):
        # Arrange
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())
        # Act
        detector.update("allocate", pid=1, resource_id="R1")
        # Assert
        snap = detector.get_state_snapshot()
        assert snap["allocations"][1] == ["R1"]

    def test_update_requests_tracks_waiting(self):
        # Arrange
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())
        # Act
        detector.update("request", pid=1, resource_id="R1")
        # Assert
        snap = detector.get_state_snapshot()
        assert snap["requests"][1] == "R1"

    def test_dining_philosophers_deadlock_detected(self):
        # Arrange - 5 philosophers holding left fork, requesting right fork
        cfg = DeadlockConfig()
        detector = DeadlockDetector(cfg, EventBus())
        for i in range(5):
            detector.update("allocate", pid=i, resource_id=f"F{i}")
        # Act
        for i in range(5):
            detector.update("request", pid=i, resource_id=f"F{(i+1)%5}")
        cycles = detector.detect()
        # Assert
        assert len(cycles) > 0
        cycle_pids = set(pid for c in cycles for pid in c)
        assert len(cycle_pids) == 5
        assert set(range(5)).issubset(cycle_pids)
