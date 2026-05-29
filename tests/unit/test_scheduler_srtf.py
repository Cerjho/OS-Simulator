# tests/unit/test_scheduler_srtf.py
"""Tests for SRTF scheduler — covers all uncovered branches."""
import pytest
from modules.process.pcb import PCB, ProcessState
from modules.process.scheduler import SRTF, create_scheduler
from core.config import SchedulerConfig
from core.interrupt import InterruptController
from core.event_bus import EventBus
from modules.process.queue_manager import QueueManager


def _make_config(**kw):
    defaults = {"algorithm": "srtf", "time_quantum": 4, "preemptive": True, "aging_interval": 50}
    defaults.update(kw)
    return SchedulerConfig(**defaults)


def _make_qm():
    ic = InterruptController()
    eb = EventBus()
    return QueueManager(ic, eb)


def _make_pcb(name, burst, arrival=0, priority=5):
    return PCB(name=name, burst_time=burst, priority=priority, memory_pages=1, arrival_time=arrival)


class TestSRTF:
    def test_select_next_empty_queue(self):
        srtf = SRTF(_make_config())
        assert srtf.select_next([], tick=0) is None

    def test_select_next_picks_shortest_remaining(self):
        srtf = SRTF(_make_config())
        p1 = _make_pcb("A", 10); p1.remaining_burst = 5
        p2 = _make_pcb("B", 8);  p2.remaining_burst = 3
        result = srtf.select_next([p1, p2], tick=0)
        assert result is p2

    def test_should_preempt_empty_ready(self):
        srtf = SRTF(_make_config())
        p1 = _make_pcb("A", 10); p1.remaining_burst = 5
        assert srtf.should_preempt(p1, [], tick=0) is False

    def test_should_preempt_when_shorter_arrives(self):
        srtf = SRTF(_make_config())
        running = _make_pcb("A", 10); running.remaining_burst = 5
        ready = _make_pcb("B", 3);   ready.remaining_burst = 2
        assert srtf.should_preempt(running, [ready], tick=0) is True

    def test_should_not_preempt_when_running_is_shorter(self):
        srtf = SRTF(_make_config())
        running = _make_pcb("A", 10); running.remaining_burst = 2
        ready = _make_pcb("B", 3);   ready.remaining_burst = 5
        assert srtf.should_preempt(running, [ready], tick=0) is False

    def test_tick_preempts_when_shorter_ready(self):
        srtf = SRTF(_make_config())
        qm = _make_qm()
        p1 = _make_pcb("A", 10, arrival=0); p1.remaining_burst = 5
        p2 = _make_pcb("B", 3, arrival=0);  p2.remaining_burst = 2
        # Admit both to READY state first
        qm.new_queue.append(p1)
        qm.new_queue.append(p2)
        qm.admit(p1)
        qm.admit(p2)
        # Dispatch p1
        qm.dispatch(p1, tick=0)
        # Tick should preempt p1 and dispatch p2
        srtf.tick(1, qm)
        assert qm.running is p2

    def test_tick_dispatches_on_idle_cpu(self):
        srtf = SRTF(_make_config())
        qm = _make_qm()
        p1 = _make_pcb("A", 5, arrival=0)
        qm.new_queue.append(p1)
        qm.admit(p1)
        srtf.tick(0, qm)
        assert qm.running is p1

    def test_tick_no_action_on_empty_queue_idle_cpu(self):
        srtf = SRTF(_make_config())
        qm = _make_qm()
        srtf.tick(0, qm)
        assert qm.running is None


class TestSchedulerFactory:
    def test_create_scheduler_unknown_algorithm(self):
        cfg = SchedulerConfig(algorithm="bogus", time_quantum=4, preemptive=False, aging_interval=50)
        with pytest.raises(ValueError, match="Unknown scheduling algorithm"):
            create_scheduler(cfg)

    def test_create_all_valid_algorithms(self):
        for algo in ["fcfs", "sjf", "srtf", "priority", "round_robin", "mlfq"]:
            cfg = SchedulerConfig(algorithm=algo, time_quantum=4, preemptive=True, aging_interval=50)
            sched = create_scheduler(cfg)
            assert sched is not None
