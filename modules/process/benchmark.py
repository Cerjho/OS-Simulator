# modules/process/benchmark.py
# Phase: 6 — Scheduling Algorithm Lab
# Owner: Scheduler Agent
"""
Benchmarking suite for comparing CPU scheduling algorithms.
Full implementation spec: OS101_AgentPlan_v2.md Section 11
"""
from __future__ import annotations
from typing import Any

from core.config import SchedulerConfig
from core.interrupt import InterruptController
from core.event_bus import EventBus
from modules.process.queue_manager import QueueManager
from modules.process.scheduler import create_scheduler
from modules.process.pcb import reset_pid_counter


class SchedulerBenchmark:
    """
    Executes consistent process workloads across multiple CPU scheduling algorithms
    to evaluate throughput, turnaround time, waiting time, and preemption overhead.
    """

    def __init__(self, scheduler_config: SchedulerConfig | None = None) -> None:
        self.base_config: SchedulerConfig | None = scheduler_config

    def run(self, processes: list[dict[str, Any]], algorithms: list[str]) -> list[dict[str, Any]]:
        """
        Run each requested scheduling algorithm against the identical process workload.

        Workload format:
          list of dicts containing keys: name, burst, priority, memory_pages, arrival_tick

        Returns:
          list of result dictionaries containing execution metrics and Gantt charts.
        """
        results: list[dict[str, Any]] = []

        for algo in algorithms:
            # Reset deterministic PID assignment for each algorithm run
            reset_pid_counter()

            # Construct specific algorithm configuration template
            time_quantum = self.base_config.time_quantum if self.base_config else 4
            aging_interval = self.base_config.aging_interval if self.base_config else 50
            preemptive = self.base_config.preemptive if self.base_config else True

            cfg = SchedulerConfig(
                algorithm=algo,
                time_quantum=time_quantum,
                aging_interval=aging_interval,
                preemptive=preemptive,
            )

            # Initialize simulation sub-components
            scheduler = create_scheduler(cfg)
            interrupt_controller = InterruptController()
            event_bus = EventBus(strict_types=False)  # Allow generic operational logging events
            qm = QueueManager(interrupt_controller, event_bus)

            # Populate new process queue
            target_count = len(processes)
            for p_dict in processes:
                qm.create_process(
                    name=p_dict.get("name", "unknown"),
                    burst_time=p_dict.get("burst", 0),
                    priority=p_dict.get("priority", 5),
                    memory_pages=p_dict.get("memory_pages", 4),
                    arrival_time=p_dict.get("arrival_tick", 0),
                )

            # Perform initial baseline admission at tick 0
            for pcb in list(qm.new_queue):
                if pcb.arrival_time <= 0:
                    if hasattr(scheduler, "admit"):
                        scheduler.admit(pcb)
                    qm.admit(pcb)

            # Trigger initial scheduler dispatching if ready
            scheduler.tick(0, qm)

            # Main simulation execution loop
            max_simulation_ticks = 20_000
            for tick in range(1, max_simulation_ticks + 1):
                # Terminate loop early if all processes complete successfully
                if len(qm.terminated) >= target_count:
                    break

                # Process admissions arriving at current tick
                for pcb in list(qm.new_queue):
                    if pcb.arrival_time == tick:
                        if hasattr(scheduler, "admit"):
                            scheduler.admit(pcb)
                        qm.admit(pcb)

                # Dispatch pending subsystem interrupts
                interrupt_controller.handle_all()

                # BUG-08 fix: Scheduler runs BEFORE execute to match kernel tick order
                # Step 3: Scheduler decides who runs next
                scheduler.tick(tick, qm)

                # Step 4: Execute active process burst unit
                qm.execute_tick(tick)

            # Extract final performance metrics
            stats = qm.get_statistics()

            # Format standardized Gantt chart records
            gantt_records = [
                {
                    "pid": g.pid,
                    "start_tick": g.start_tick,
                    "end_tick": g.end_tick,
                    "color": g.color,
                }
                for g in qm.gantt_log
            ]

            results.append({
                "algorithm": algo,
                "avg_waiting_time": stats["avg_waiting_time"],
                "avg_turnaround_time": stats["avg_turnaround_time"],
                "avg_response_time": stats["avg_response_time"],
                "throughput": stats["throughput"],
                "context_switches": stats["total_context_switches"],
                "gantt": gantt_records,
            })

        return results
