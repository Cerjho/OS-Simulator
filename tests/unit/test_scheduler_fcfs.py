# tests/unit/test_scheduler_fcfs.py
"""
Unit tests for scheduler_fcfs.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import SchedulerConfig
from core.interrupt import InterruptController
from core.event_bus import EventBus
from modules.process.pcb import PCB, reset_pid_counter
from modules.process.scheduler import FCFS
from modules.process.queue_manager import QueueManager


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestFCFSScheduler:

    def test_fcfs_selects_earliest_arrival(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="fcfs")
        scheduler = FCFS(cfg)
        pcb1 = PCB(name="P1", burst_time=5, arrival_time=2)
        pcb2 = PCB(name="P2", burst_time=5, arrival_time=1)
        # Act
        selected = scheduler.select_next([pcb1, pcb2], tick=3)
        # Assert
        assert selected == pcb2, f"Expected {pcb2}, got {selected}"

    def test_fcfs_nonpreemptive_never_preempts(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="fcfs")
        scheduler = FCFS(cfg)
        running = PCB(name="P1", burst_time=10)
        ready = PCB(name="P2", burst_time=2, arrival_time=0)
        # Act
        preempt = scheduler.should_preempt(running, [ready], tick=5)
        # Assert
        assert preempt is False

    def test_fcfs_gantt_order_matches_arrival(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="fcfs")
        scheduler = FCFS(cfg)
        qm = QueueManager(InterruptController(), EventBus())
        qm.create_process("P1", burst_time=2, priority=5, memory_pages=4, arrival_time=0)
        qm.create_process("P2", burst_time=2, priority=5, memory_pages=4, arrival_time=0)
        for p in list(qm.new_queue):
            qm.admit(p)
        # Act
        for t in range(1, 6):
            qm.execute_tick(t)
            scheduler.tick(t, qm)
        # Assert
        assert len(qm.gantt_log) >= 2
        assert qm.gantt_log[0].pid == 1
        assert qm.gantt_log[1].pid == 2

    def test_fcfs_avg_wait_standard_workload(self):
        # Arrange - Textbook standard mix yielding exactly 8.33 average wait
        qm = QueueManager(InterruptController(), EventBus())
        qm.create_process("P1", burst_time=10, priority=5, memory_pages=4, arrival_time=0)
        qm.create_process("P2", burst_time=5, priority=5, memory_pages=4, arrival_time=0)
        qm.create_process("P3", burst_time=8, priority=5, memory_pages=4, arrival_time=0)
        for p in list(qm.new_queue):
            qm.admit(p)
        scheduler = FCFS(SchedulerConfig(algorithm="fcfs"))
        scheduler.tick(0, qm)
        # Act
        for t in range(1, 30):
            qm.execute_tick(t)
            scheduler.tick(t, qm)
        # Assert
        stats = qm.get_statistics()
        assert abs(stats["avg_waiting_time"] - 8.33) <= 0.1, f"Expected 8.33, got {stats['avg_waiting_time']}"

    def test_fcfs_avg_turnaround_standard_workload(self):
        # Arrange - Textbook standard mix yielding exactly 16.0 average turnaround
        qm = QueueManager(InterruptController(), EventBus())
        qm.create_process("P1", burst_time=10, priority=5, memory_pages=4, arrival_time=0)
        qm.create_process("P2", burst_time=5, priority=5, memory_pages=4, arrival_time=0)
        qm.create_process("P3", burst_time=8, priority=5, memory_pages=4, arrival_time=0)
        for p in list(qm.new_queue):
            qm.admit(p)
        scheduler = FCFS(SchedulerConfig(algorithm="fcfs"))
        scheduler.tick(0, qm)
        # Act
        for t in range(1, 30):
            qm.execute_tick(t)
            scheduler.tick(t, qm)
        # Assert
        stats = qm.get_statistics()
        assert abs(stats["avg_turnaround_time"] - 16.0) <= 0.1, f"Expected 16.0, got {stats['avg_turnaround_time']}"
