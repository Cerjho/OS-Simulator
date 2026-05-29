# tests/unit/test_scheduler_rr.py
"""
Unit tests for scheduler_rr.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import SchedulerConfig
from core.interrupt import InterruptController
from core.event_bus import EventBus
from modules.process.pcb import PCB, reset_pid_counter
from modules.process.scheduler import RoundRobin
from modules.process.queue_manager import QueueManager


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestRoundRobinScheduler:

    def test_rr_preempts_at_quantum_boundary(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="round_robin", time_quantum=2)
        scheduler = RoundRobin(cfg)
        running = PCB(name="P1", burst_time=5)
        running.time_slice_used = 2
        # Act
        preempt = scheduler.should_preempt(running, [], tick=3)
        # Assert
        assert preempt is True

    def test_rr_preempted_process_goes_to_back_of_queue(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="round_robin", time_quantum=2)
        scheduler = RoundRobin(cfg)
        qm = QueueManager(InterruptController(), EventBus())
        qm.create_process("P1", burst_time=5, priority=5, memory_pages=4, arrival_time=0)
        qm.create_process("P2", burst_time=5, priority=5, memory_pages=4, arrival_time=0)
        for p in list(qm.new_queue):
            qm.admit(p)
        scheduler.tick(0, qm)
        assert qm.running.pid == 1
        # Act
        qm.execute_tick(1)
        scheduler.tick(1, qm)
        qm.execute_tick(2)
        scheduler.tick(2, qm) # P1 hits quantum=2, preempts
        # Assert
        assert qm.running.pid == 2
        assert qm.ready_queue[-1].pid == 1

    def test_rr_time_slice_resets_after_preemption(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="round_robin", time_quantum=2)
        scheduler = RoundRobin(cfg)
        qm = QueueManager(InterruptController(), EventBus())
        qm.create_process("P1", burst_time=5, priority=5, memory_pages=4, arrival_time=0)
        qm.create_process("P2", burst_time=5, priority=5, memory_pages=4, arrival_time=0)
        for p in list(qm.new_queue):
            qm.admit(p)
        scheduler.tick(0, qm)
        # Act
        qm.execute_tick(1)
        scheduler.tick(1, qm)
        qm.execute_tick(2)
        scheduler.tick(2, qm)
        # Assert
        p1 = qm.ready_queue[-1]
        assert p1.pid == 1
        assert p1.time_slice_used == 0

    def test_rr_no_preemption_before_quantum_expires(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="round_robin", time_quantum=4)
        scheduler = RoundRobin(cfg)
        running = PCB(name="P1", burst_time=5)
        running.time_slice_used = 2
        # Act
        preempt = scheduler.should_preempt(running, [], tick=3)
        # Assert
        assert preempt is False

    def test_rr_single_process_runs_to_completion(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="round_robin", time_quantum=2)
        scheduler = RoundRobin(cfg)
        qm = QueueManager(InterruptController(), EventBus())
        qm.create_process("P1", burst_time=3, priority=5, memory_pages=4, arrival_time=0)
        for p in list(qm.new_queue):
            qm.admit(p)
        scheduler.tick(0, qm)
        # Act
        for t in range(1, 5):
            if qm.running:
                qm.execute_tick(t)
            scheduler.tick(t, qm)
        # Assert
        assert len(qm.terminated) == 1
        assert qm.terminated[0].pid == 1

    def test_rr_context_switch_count_correct(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="round_robin", time_quantum=1)
        scheduler = RoundRobin(cfg)
        qm = QueueManager(InterruptController(), EventBus())
        qm.create_process("P1", burst_time=2, priority=5, memory_pages=4, arrival_time=0)
        qm.create_process("P2", burst_time=2, priority=5, memory_pages=4, arrival_time=0)
        for p in list(qm.new_queue):
            qm.admit(p)
        scheduler.tick(0, qm)
        # Act
        for t in range(1, 6):
            if qm.running:
                qm.execute_tick(t)
            scheduler.tick(t, qm)
        # Assert
        stats = qm.get_statistics()
        assert stats["total_context_switches"] >= 3
