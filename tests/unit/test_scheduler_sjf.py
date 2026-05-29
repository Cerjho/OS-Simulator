# tests/unit/test_scheduler_sjf.py
"""
Unit tests for scheduler_sjf.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import SchedulerConfig
from core.interrupt import InterruptController
from core.event_bus import EventBus
from modules.process.pcb import PCB, reset_pid_counter
from modules.process.scheduler import SJF
from modules.process.queue_manager import QueueManager


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestSJFScheduler:

    def test_sjf_selects_shortest_burst(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="sjf")
        scheduler = SJF(cfg)
        p1 = PCB(name="P1", burst_time=10)
        p2 = PCB(name="P2", burst_time=2)
        p3 = PCB(name="P3", burst_time=5)
        # Act
        selected = scheduler.select_next([p1, p2, p3], tick=1)
        # Assert
        assert selected == p2

    def test_sjf_tie_breaking_order(self):
        # Arrange - smallest burst; tie → smallest arrival_time → smallest pid
        cfg = SchedulerConfig(algorithm="sjf")
        scheduler = SJF(cfg)
        p1 = PCB(name="P1", burst_time=5, arrival_time=2)
        p2 = PCB(name="P2", burst_time=5, arrival_time=1)
        # Act
        selected = scheduler.select_next([p1, p2], tick=3)
        # Assert
        assert selected == p2

    def test_sjf_nonpreemptive_never_preempts(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="sjf")
        scheduler = SJF(cfg)
        running = PCB(name="P1", burst_time=10)
        ready = PCB(name="P2", burst_time=1) # shorter burst
        # Act
        preempt = scheduler.should_preempt(running, [ready], tick=2)
        # Assert
        assert preempt is False

    def test_sjf_dispatches_idle_cpu(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="sjf")
        scheduler = SJF(cfg)
        qm = QueueManager(InterruptController(), EventBus())
        qm.create_process("P1", burst_time=3, priority=5, memory_pages=4, arrival_time=0)
        for p in list(qm.new_queue):
            qm.admit(p)
        # Act
        scheduler.tick(0, qm)
        # Assert
        assert qm.running is not None
        assert qm.running.pid == 1

    def test_sjf_gantt_order_optimal(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="sjf")
        scheduler = SJF(cfg)
        qm = QueueManager(InterruptController(), EventBus())
        qm.create_process("P1", burst_time=10, priority=5, memory_pages=4, arrival_time=0)
        qm.create_process("P2", burst_time=2, priority=5, memory_pages=4, arrival_time=0)
        for p in list(qm.new_queue):
            qm.admit(p)
        scheduler.tick(0, qm) # P2 selected because burst=2 < 10
        # Act
        for t in range(1, 15):
            qm.execute_tick(t)
            scheduler.tick(t, qm)
        # Assert
        assert len(qm.terminated) == 2
        assert qm.terminated[0].pid == 2 # Shortest job finished first
