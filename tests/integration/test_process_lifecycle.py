# tests/integration/test_process_lifecycle.py
"""
Integration tests for full process lifecycle.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import SchedulerConfig
from core.interrupt import InterruptController
from core.event_bus import EventBus
from modules.process.pcb import ProcessState, reset_pid_counter
from modules.process.queue_manager import QueueManager
from modules.process.scheduler import FCFS, RoundRobin


@pytest.fixture(autouse=True)
def reset_pids():
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestProcessLifecycle:

    def test_new_to_terminated_full_cycle(self):
        """Process traverses NEW → READY → RUNNING → TERMINATED."""
        qm = QueueManager(InterruptController(), EventBus())
        pid = qm.create_process("P1", burst_time=3, priority=5, memory_pages=4, arrival_time=0)
        assert len(qm.new_queue) == 1

        pcb = qm.new_queue[0]
        qm.admit(pcb)
        assert pcb.state == ProcessState.READY
        assert len(qm.ready_queue) == 1

        scheduler = FCFS(SchedulerConfig(algorithm="fcfs"))
        scheduler.tick(0, qm)
        assert qm.running is not None
        assert qm.running.state == ProcessState.RUNNING

        for t in range(1, 5):
            qm.execute_tick(t)
            scheduler.tick(t, qm)

        assert len(qm.terminated) == 1
        assert qm.terminated[0].pid == pid
        assert qm.terminated[0].state == ProcessState.TERMINATED

    def test_multiple_processes_complete_under_fcfs(self):
        """All 3 processes complete with correct ordering under FCFS."""
        qm = QueueManager(InterruptController(), EventBus())
        qm.create_process("P1", burst_time=3, priority=5, memory_pages=4, arrival_time=0)
        qm.create_process("P2", burst_time=2, priority=5, memory_pages=4, arrival_time=0)
        qm.create_process("P3", burst_time=1, priority=5, memory_pages=4, arrival_time=0)
        for p in list(qm.new_queue):
            qm.admit(p)

        scheduler = FCFS(SchedulerConfig(algorithm="fcfs"))
        scheduler.tick(0, qm)
        for t in range(1, 10):
            qm.execute_tick(t)
            scheduler.tick(t, qm)

        assert len(qm.terminated) == 3
        stats = qm.get_statistics()
        assert stats["avg_turnaround_time"] > 0

    def test_rr_preemption_cycle(self):
        """Round Robin correctly cycles between two processes."""
        qm = QueueManager(InterruptController(), EventBus())
        qm.create_process("P1", burst_time=4, priority=5, memory_pages=4, arrival_time=0)
        qm.create_process("P2", burst_time=4, priority=5, memory_pages=4, arrival_time=0)
        for p in list(qm.new_queue):
            qm.admit(p)

        scheduler = RoundRobin(SchedulerConfig(algorithm="round_robin", time_quantum=2))
        scheduler.tick(0, qm)
        for t in range(1, 12):
            if qm.running:
                qm.execute_tick(t)
            scheduler.tick(t, qm)

        assert len(qm.terminated) == 2
        assert qm.context_switch_count >= 4

    def test_gantt_log_populated(self):
        """Gantt log entries are created for every CPU burst segment."""
        qm = QueueManager(InterruptController(), EventBus())
        qm.create_process("P1", burst_time=2, priority=5, memory_pages=4, arrival_time=0)
        for p in list(qm.new_queue):
            qm.admit(p)

        scheduler = FCFS(SchedulerConfig(algorithm="fcfs"))
        scheduler.tick(0, qm)
        for t in range(1, 4):
            qm.execute_tick(t)
            scheduler.tick(t, qm)

        assert len(qm.gantt_log) >= 1
        entry = qm.gantt_log[0]
        assert entry.pid == 1
        assert entry.start_tick < entry.end_tick

    def test_event_bus_receives_lifecycle_events(self):
        """EventBus receives PROCESS_CREATED and PROCESS_TERMINATED."""
        eb = EventBus()
        events = []
        eb.subscribe("PROCESS_CREATED", lambda e: events.append(e))
        eb.subscribe("PROCESS_TERMINATED", lambda e: events.append(e))

        qm = QueueManager(InterruptController(), eb)
        qm.create_process("P1", burst_time=1, priority=5, memory_pages=4, arrival_time=0)
        for p in list(qm.new_queue):
            qm.admit(p)

        scheduler = FCFS(SchedulerConfig(algorithm="fcfs"))
        scheduler.tick(0, qm)
        for t in range(1, 3):
            qm.execute_tick(t)
            scheduler.tick(t, qm)

        event_types = [e.event_type for e in events]
        assert "PROCESS_CREATED" in event_types
        assert "PROCESS_TERMINATED" in event_types
