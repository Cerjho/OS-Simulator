# tests/unit/test_scheduler_priority.py
"""
Unit tests for scheduler_priority.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import SchedulerConfig
from core.interrupt import InterruptController
from core.event_bus import EventBus
from modules.process.pcb import PCB, ProcessState, reset_pid_counter
from modules.process.scheduler import PriorityScheduler
from modules.process.queue_manager import QueueManager


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestPriorityScheduler:

    def test_priority_selects_highest_priority_value(self):
        # Arrange - 0 is highest priority
        cfg = SchedulerConfig(algorithm="priority")
        scheduler = PriorityScheduler(cfg)
        p1 = PCB(name="P1", burst_time=5, priority=5)
        p2 = PCB(name="P2", burst_time=5, priority=1)
        p3 = PCB(name="P3", burst_time=5, priority=9)
        # Act
        selected = scheduler.select_next([p1, p2, p3], tick=1)
        # Assert
        assert selected == p2

    def test_priority_tie_breaking_order(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="priority")
        scheduler = PriorityScheduler(cfg)
        p1 = PCB(name="P1", burst_time=5, priority=2, arrival_time=5)
        p2 = PCB(name="P2", burst_time=5, priority=2, arrival_time=1)
        # Act
        selected = scheduler.select_next([p1, p2], tick=6)
        # Assert
        assert selected == p2

    def test_priority_preemptive_overrides_running(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="priority", preemptive=True)
        scheduler = PriorityScheduler(cfg)
        running = PCB(name="P1", burst_time=10, priority=5)
        ready = PCB(name="P2", burst_time=5, priority=1)
        # Act
        preempt = scheduler.should_preempt(running, [ready], tick=2)
        # Assert
        assert preempt is True

    def test_priority_nonpreemptive_ignores_higher_ready(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="priority", preemptive=False)
        scheduler = PriorityScheduler(cfg)
        running = PCB(name="P1", burst_time=10, priority=5)
        ready = PCB(name="P2", burst_time=5, priority=1)
        # Act
        preempt = scheduler.should_preempt(running, [ready], tick=2)
        # Assert
        assert preempt is False

    def test_priority_aging_prevents_starvation(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="priority", aging_interval=10)
        scheduler = PriorityScheduler(cfg)
        qm = QueueManager(InterruptController(), EventBus())
        p = PCB(name="P1", burst_time=5, priority=5)
        p.state = ProcessState.READY
        qm.ready_queue.append(p)
        # Act
        scheduler.tick(10, qm)
        # Assert
        assert p.priority == 4
