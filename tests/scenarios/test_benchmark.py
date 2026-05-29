# tests/scenarios/test_benchmark.py
"""
Scenario tests for scheduler benchmarking.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import SchedulerConfig
from core.interrupt import InterruptController
from core.event_bus import EventBus
from modules.process.pcb import reset_pid_counter
from modules.process.queue_manager import QueueManager
from modules.process.scheduler import create_scheduler


@pytest.fixture(autouse=True)
def reset_pids():
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestBenchmarkScenario:

    def _run_workload(self, algorithm: str, **kwargs):
        """Helper: run standard 5-process workload under a given algorithm."""
        reset_pid_counter()
        cfg = SchedulerConfig(algorithm=algorithm, **kwargs)
        scheduler = create_scheduler(cfg)
        qm = QueueManager(InterruptController(), EventBus())

        workload = [
            ("P1", 3, 5, 2, 0),
            ("P2", 8, 3, 4, 0),
            ("P3", 12, 7, 6, 0),
            ("P4", 20, 2, 8, 0),
            ("P5", 5, 9, 2, 0),
        ]
        for name, burst, prio, pages, arr in workload:
            qm.create_process(name, burst_time=burst, priority=prio, memory_pages=pages, arrival_time=arr)
        for p in list(qm.new_queue):
            qm.admit(p)

        scheduler.tick(0, qm)
        for t in range(1, 60):
            if qm.running:
                qm.execute_tick(t)
            scheduler.tick(t, qm)

        return qm.get_statistics()

    def test_fcfs_completes_all_processes(self):
        stats = self._run_workload("fcfs")
        assert stats["avg_turnaround_time"] > 0
        assert stats["throughput"] > 0

    def test_sjf_has_lower_avg_wait_than_fcfs(self):
        fcfs_stats = self._run_workload("fcfs")
        sjf_stats = self._run_workload("sjf")
        # SJF should generally produce lower or equal avg waiting time
        assert sjf_stats["avg_waiting_time"] <= fcfs_stats["avg_waiting_time"] + 1.0

    def test_rr_produces_more_context_switches_than_fcfs(self):
        fcfs_stats = self._run_workload("fcfs")
        rr_stats = self._run_workload("round_robin", time_quantum=2)
        assert rr_stats["total_context_switches"] >= fcfs_stats["total_context_switches"]

    def test_priority_schedules_highest_priority_first(self):
        reset_pid_counter()
        cfg = SchedulerConfig(algorithm="priority")
        scheduler = create_scheduler(cfg)
        qm = QueueManager(InterruptController(), EventBus())

        qm.create_process("LOW", burst_time=5, priority=9, memory_pages=2, arrival_time=0)
        qm.create_process("HIGH", burst_time=5, priority=1, memory_pages=2, arrival_time=0)
        for p in list(qm.new_queue):
            qm.admit(p)

        scheduler.tick(0, qm)
        # HIGH priority (1) should be dispatched first
        assert qm.running is not None
        assert qm.running.name == "HIGH"

    def test_mlfq_demotes_cpu_bound_processes(self):
        reset_pid_counter()
        cfg = SchedulerConfig(algorithm="mlfq", time_quantum=2)
        scheduler = create_scheduler(cfg)
        qm = QueueManager(InterruptController(), EventBus())

        qm.create_process("CPU_HOG", burst_time=20, priority=5, memory_pages=4, arrival_time=0)
        for p in list(qm.new_queue):
            qm.admit(p)

        scheduler.tick(0, qm)
        for t in range(1, 15):
            if qm.running:
                qm.execute_tick(t)
            scheduler.tick(t, qm)

        # After multiple quantum exhaustions, the process should be demoted
        pcbs = qm.get_all_processes() + qm.terminated
        cpu_hog = [p for p in pcbs if p.name == "CPU_HOG"][0]
        assert cpu_hog.mlfq_queue_level >= 1 or cpu_hog.state.value == "terminated"
