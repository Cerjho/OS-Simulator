# experiments/runner.py
# Phase: 9 — Experiments & Benchmarking
# Owner: Experiment Agent
"""
Automated batch execution framework for comprehensive multi-dimensional simulation runs.
Evaluates 4 core process workloads across 6 precise experimental scheduling configurations.
Full implementation spec: OS101_AgentPlan_v2.md Section 14
"""
from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Any, TYPE_CHECKING
import yaml

from core.kernel import Kernel
from core.config import SimConfig, load_config

if TYPE_CHECKING:
    pass


class ExperimentRunner:
    """
    Orchestrates continuous comparative benchmarking simulations across pre-configured evaluation conditions.
    """

    def __init__(self, kernel: Kernel | None = None) -> None:
        self.reference_kernel: Kernel | None = kernel

    async def run_all(self) -> dict[str, dict[str, dict[str, Any]]]:
        """
        Executes all 4 target evaluation workloads across precisely 6 distinct hardware algorithm conditions.
        
        Conditions evaluated:
          1. base_fcfs      (FCFS CPU, FIFO paging, FCFS disk)
          2. opt_sjf        (SJF CPU, Optimal paging, SSTF disk)
          3. real_rr        (Round Robin q=4, LRU paging, C-SCAN disk)
          4. priority_aging (Priority tier, Clock paging, LOOK disk)
          5. mlfq_thrash    (MLFQ CPU, FIFO paging, FCFS disk)
          6. memory_tight   (Round Robin q=2, LRU frames=16, SCAN disk)

        Returns nested mapping dictionary:
          results[workload_name][condition_name] = Section 17.2 telemetry metrics dict
        """
        workloads_to_run = ["standard_mix", "io_heavy", "memory_pressure", "deadlock_demo"]
        
        conditions_map = {
            "base_fcfs": {"cpu_algo": "fcfs", "mem_algo": "fifo", "disk_algo": "fcfs", "q": 4, "frames": 64},
            "opt_sjf": {"cpu_algo": "sjf", "mem_algo": "optimal", "disk_algo": "sstf", "q": 4, "frames": 64},
            "real_rr": {"cpu_algo": "round_robin", "mem_algo": "lru", "disk_algo": "c-scan", "q": 4, "frames": 64},
            "priority_aging": {"cpu_algo": "priority", "mem_algo": "clock", "disk_algo": "look", "q": 4, "frames": 64},
            "mlfq_thrash": {"cpu_algo": "mlfq", "mem_algo": "fifo", "disk_algo": "fcfs", "q": 4, "frames": 64},
            "memory_tight": {"cpu_algo": "round_robin", "mem_algo": "lru", "disk_algo": "scan", "q": 2, "frames": 16},
        }

        results_matrix: dict[str, dict[str, dict[str, Any]]] = {}
        temp_config_path = Path("experiments/temp_run.yaml")

        for workload_stem in workloads_to_run:
            results_matrix[workload_stem] = {}
            workload_file = Path(f"experiments/workloads/{workload_stem}.yaml")
            processes_spec: list[dict[str, Any]] = []

            if workload_file.exists():
                try:
                    parsed_yml = yaml.safe_load(workload_file.read_text()) or {}
                    processes_spec = parsed_yml.get("processes", [])
                except Exception:
                    pass

            for cond_name, params in conditions_map.items():
                # Construct bespoke simulation configuration mapping matching exact experimental conditions
                try:
                    cfg_dict = {
                        "clock": {"tick_rate_ms": 100, "max_ticks": 10000},
                        "cpu": {"cores": 1, "context_switch_cost": 2},
                        "scheduler": {"algorithm": params["cpu_algo"], "time_quantum": params["q"]},
                        "memory": {"algorithm": params["mem_algo"], "total_frames": params["frames"]},
                        "disk": {"scheduling": params["disk_algo"]},
                        "processes": {"initial_load": 0, "auto_spawn": False},
                        # BUG-29 fix: Include all required config sections
                        "filesystem": {"type": "fat", "total_blocks": 512, "block_size_kb": 4},
                        "deadlock": {"detection_interval": 10, "recovery_strategy": "terminate_youngest"},
                        "logging": {"level": "WARNING", "log_to_file": False},
                    }
                    temp_config_path.parent.mkdir(parents=True, exist_ok=True)
                    temp_config_path.write_text(yaml.dump(cfg_dict))
                except Exception as e:
                    print(f"[ExperimentRunner] Config serialization warning: {e}")

                # Initialize fresh decoupled simulation Kernel context
                eval_kernel = Kernel(str(temp_config_path))
                # Invoke dependency initialization layer natively
                if hasattr(eval_kernel, "_init_subsystems"):
                    await eval_kernel._init_subsystems()

                # Sequentially inject specified process footprints mapping dynamic execution demands
                injected_count = 0
                for spec in processes_spec:
                    pid = eval_kernel.inject_process(spec)
                    injected_count += 1
                    # BUG-47 fix: Submit IO requests for workload-defined cylinders
                    io_cyls = spec.get("io_cylinders", [])
                    if io_cyls and eval_kernel.io_manager:
                        for cyl in io_cyls:
                            eval_kernel.io_manager.submit_io(
                                pid=pid, device_id="disk0", cylinder=cyl, operation="read"
                            )

                # Advance internal simulation clock synchronously up to bounded completion horizons
                max_execution_horizon = 120
                for _ in range(max_execution_horizon):
                    await eval_kernel.step()
                    # Terminate step evaluation early if all injected processes resolve execution lifecycles
                    if eval_kernel.process_manager and hasattr(eval_kernel.process_manager, "terminated"):
                        if len(eval_kernel.process_manager.terminated) >= max(injected_count, 1):
                            break

                # Extract real telemetry metrics from actual simulation run
                base_cpu_util = 0.0
                mem_util = 0.0
                pf_rate = 0.0
                if eval_kernel.metrics_collector:
                    base_cpu_util = eval_kernel.metrics_collector.cpu_utilization()
                    mem_util = eval_kernel.metrics_collector.current_memory_utilization()
                    pf_rate = eval_kernel.metrics_collector.current_page_fault_rate()

                # Extract process scheduling statistics from real simulation data
                stats = {"avg_turnaround_time": 0.0, "avg_waiting_time": 0.0, "throughput": 0.0}
                if eval_kernel.process_manager:
                    stats = eval_kernel.process_manager.get_statistics()

                metrics_snapshot = {
                    "cpu_utilization": base_cpu_util,
                    "memory_utilization": mem_util,
                    "page_fault_rate": pf_rate,
                    "throughput": stats.get("throughput", 0.0),
                    "turnaround_time": stats.get("avg_turnaround_time", 0.0),
                    "waiting_time": stats.get("avg_waiting_time", 0.0),
                    "total_ticks": eval_kernel.clock.tick_count,
                    "condition": cond_name,
                }

                results_matrix[workload_stem][cond_name] = metrics_snapshot

        # Remove temporary execution profile configuration scripts to maintain workspace cleanliness
        if temp_config_path.exists():
            try:
                temp_config_path.unlink()
            except Exception:
                pass

        return results_matrix
