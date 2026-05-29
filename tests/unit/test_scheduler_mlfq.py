# tests/unit/test_scheduler_mlfq.py
"""
Unit tests for scheduler_mlfq.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import SchedulerConfig
from core.interrupt import InterruptController
from core.event_bus import EventBus
from modules.process.pcb import PCB, ProcessState, reset_pid_counter
from modules.process.scheduler import MLFQ
from modules.process.queue_manager import QueueManager


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestMLFQScheduler:

    def test_mlfq_new_process_enters_queue_0(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="mlfq")
        scheduler = MLFQ(cfg)
        pcb = PCB(name="P1", burst_time=10)
        # Act
        scheduler.admit(pcb)
        # Assert
        assert pcb.mlfq_queue_level == 0

    def test_mlfq_full_quantum_causes_demotion(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="mlfq", time_quantum=2)
        scheduler = MLFQ(cfg)
        pcb = PCB(name="P1", burst_time=10)
        scheduler.admit(pcb)
        # Act
        scheduler.on_full_quantum_used(pcb)
        # Assert
        assert pcb.mlfq_queue_level == 1

    def test_mlfq_demotion_capped_at_level_2(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="mlfq", time_quantum=2)
        scheduler = MLFQ(cfg)
        pcb = PCB(name="P1", burst_time=10)
        scheduler.admit(pcb)
        # Act
        scheduler.on_full_quantum_used(pcb)
        scheduler.on_full_quantum_used(pcb)
        scheduler.on_full_quantum_used(pcb)
        # Assert
        assert pcb.mlfq_queue_level == 2

    def test_mlfq_level_0_preempts_level_1(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="mlfq")
        scheduler = MLFQ(cfg)
        running = PCB(name="P1", burst_time=10)
        running.mlfq_queue_level = 1
        ready = PCB(name="P2", burst_time=5)
        ready.mlfq_queue_level = 0
        # Act
        preempt = scheduler.should_preempt(running, [ready], tick=5)
        # Assert
        assert preempt is True

    def test_mlfq_level_0_preempts_level_2(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="mlfq")
        scheduler = MLFQ(cfg)
        running = PCB(name="P1", burst_time=10)
        running.mlfq_queue_level = 2
        ready = PCB(name="P2", burst_time=5)
        ready.mlfq_queue_level = 0
        # Act
        preempt = scheduler.should_preempt(running, [ready], tick=5)
        # Assert
        assert preempt is True

    def test_mlfq_aging_promotes_from_level_1(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="mlfq", aging_interval=10)
        scheduler = MLFQ(cfg)
        qm = QueueManager(InterruptController(), EventBus())
        pcb = PCB(name="P1", burst_time=10)
        pcb.state = ProcessState.READY
        pcb.mlfq_queue_level = 1
        qm.ready_queue.append(pcb)
        # Act
        scheduler.tick(10, qm)
        # Assert
        assert pcb.mlfq_queue_level == 0

    def test_mlfq_aging_promotes_from_level_2(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="mlfq", aging_interval=10)
        scheduler = MLFQ(cfg)
        qm = QueueManager(InterruptController(), EventBus())
        pcb = PCB(name="P1", burst_time=10)
        pcb.state = ProcessState.READY
        pcb.mlfq_queue_level = 2
        qm.ready_queue.append(pcb)
        # Act
        scheduler.tick(10, qm)
        # Assert
        assert pcb.mlfq_queue_level == 1

    def test_mlfq_aging_does_not_exceed_level_0(self):
        # Arrange
        cfg = SchedulerConfig(algorithm="mlfq", aging_interval=10)
        scheduler = MLFQ(cfg)
        qm = QueueManager(InterruptController(), EventBus())
        pcb = PCB(name="P1", burst_time=10)
        pcb.state = ProcessState.READY
        pcb.mlfq_queue_level = 0
        qm.ready_queue.append(pcb)
        # Act
        scheduler.tick(10, qm)
        # Assert
        assert pcb.mlfq_queue_level == 0
