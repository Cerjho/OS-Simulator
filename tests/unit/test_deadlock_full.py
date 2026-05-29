# tests/unit/test_deadlock_full.py
"""Comprehensive deadlock tests for 100% coverage."""
import pytest
from modules.sync.deadlock import DeadlockDetector
from core.config import DeadlockConfig
from core.event_bus import EventBus


def _cfg(**kw):
    d = {"detection_interval": 10, "recovery_strategy": "terminate_youngest"}
    d.update(kw)
    return DeadlockConfig(**d)


def _dd(**kw):
    return DeadlockDetector(_cfg(**kw), EventBus())


class TestUpdate:
    def test_allocate(self):
        dd = _dd()
        dd.update("allocate", pid=1, resource_id="R1")
        assert "R1" in dd._allocations[1]

    def test_allocate_duplicate_ignored(self):
        dd = _dd()
        dd.update("allocate", 1, "R1")
        dd.update("allocate", 1, "R1")
        assert dd._allocations[1].count("R1") == 1

    def test_allocate_clears_pending_request(self):
        dd = _dd()
        dd.update("request", 1, "R1")
        assert dd._requests[1] == "R1"
        dd.update("allocate", 1, "R1")
        assert dd._requests[1] is None

    def test_request(self):
        dd = _dd()
        dd.update("request", 1, "R1")
        assert dd._requests[1] == "R1"

    def test_release_allocation(self):
        dd = _dd()
        dd.update("allocate", 1, "R1")
        dd.update("release", 1, "R1")
        assert "R1" not in dd._allocations[1]

    def test_release_clears_request(self):
        dd = _dd()
        dd.update("request", 1, "R1")
        dd.update("release", 1, "R1")
        assert dd._requests[1] is None

    def test_release_nonexistent_ok(self):
        dd = _dd()
        dd.update("release", 1, "R1")  # Should not raise


class TestDetect:
    def test_no_deadlock(self):
        dd = _dd()
        dd.update("allocate", 1, "R1")
        dd.update("allocate", 2, "R2")
        assert dd.detect() == []
        assert dd._detected is False

    def test_circular_deadlock(self):
        dd = _dd()
        dd.update("allocate", 1, "R1")
        dd.update("allocate", 2, "R2")
        dd.update("request", 1, "R2")
        dd.update("request", 2, "R1")
        cycles = dd.detect()
        assert len(cycles) > 0
        assert dd._detected is True


class TestBankers:
    def test_safe_state(self):
        dd = _dd()
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
        assert dd.is_safe_state(available, allocation, need) is True

    def test_unsafe_state(self):
        dd = _dd()
        available = {"A": 0}
        allocation = {0: {"A": 1}, 1: {"A": 1}}
        need = {0: {"A": 2}, 1: {"A": 2}}
        assert dd.is_safe_state(available, allocation, need) is False

    def test_safe_trivial(self):
        dd = _dd()
        assert dd.is_safe_state({"A": 5}, {}, {}) is True


class TestRecover:
    def test_terminate_youngest(self):
        dd = _dd()
        dd.update("allocate", 1, "R1")
        dd.update("allocate", 2, "R2")
        dd.update("request", 1, "R2")
        dd.update("request", 2, "R1")
        cycles = dd.detect()
        affected = dd.recover(cycles, "terminate_youngest")
        assert 2 in affected
        assert dd._detected is False

    def test_terminate_lowest(self):
        dd = _dd()
        dd.update("allocate", 1, "R1")
        dd.update("allocate", 2, "R2")
        dd.update("request", 1, "R2")
        dd.update("request", 2, "R1")
        cycles = dd.detect()
        affected = dd.recover(cycles, "terminate_lowest")
        assert len(affected) > 0

    def test_resource_preempt(self):
        dd = _dd()
        dd.update("allocate", 1, "R1")
        dd.update("allocate", 2, "R2")
        dd.update("request", 1, "R2")
        dd.update("request", 2, "R1")
        cycles = dd.detect()
        affected = dd.recover(cycles, "resource_preempt")
        assert len(affected) > 0

    def test_recover_empty_cycle(self):
        dd = _dd()
        affected = dd.recover([[]], "terminate_youngest")
        assert affected == []

    def test_recover_clears_state(self):
        dd = _dd()
        dd.update("allocate", 1, "R1")
        dd.update("allocate", 2, "R2")
        dd.update("request", 1, "R2")
        dd.update("request", 2, "R1")
        cycles = dd.detect()
        dd.recover(cycles, "terminate_youngest")
        assert dd._detected is False
        assert dd._cached_cycles == []


class TestSnapshot:
    def test_get_state_snapshot(self):
        dd = _dd()
        dd.update("allocate", 1, "R1")
        s = dd.get_state_snapshot()
        assert "detected" in s
        assert "allocations" in s
        assert "requests" in s


class TestTick:
    def test_tick_updates_current_tick(self):
        dd = _dd()
        dd.tick(42)
        assert dd._current_tick == 42
