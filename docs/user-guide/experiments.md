# Running Experiments

OS Simulator includes an automated benchmarking framework designed to run headless simulations across various configurations and workloads. This is useful for gathering empirical data to compare textbook algorithms.

## The Benchmark Framework

The framework is located in `experiments/`. It consists of two main scripts:

1.  `runner.py`: Executes the simulation multiple times, varying the configuration according to predefined workload definitions. It bypasses the real-time clock and runs as fast as the CPU allows.
2.  `report.py`: Parses the raw JSON output from the runner and generates formatted CSV and Markdown reports for analysis.

## Workload Definitions

Workloads are defined as YAML files in `experiments/workloads/`. A workload specifies the exact sequence of processes, their arrival times, burst times, memory requirements, and I/O profiles.

Included workloads:
*   `standard_mix.yaml`: A balanced mix of CPU-bound and I/O-bound processes.
*   `pure_compute.yaml`: CPU-bound tasks with no I/O designed to test CPU scheduler efficiency.
*   `io_heavy.yaml`: Processes that frequently block for disk reads/writes.
*   `memory_pressure.yaml`: Processes with large memory footprints designed to trigger thrashing.
*   `deadlock_demo.yaml`: Specific resource request patterns designed to induce circular waits.
*   `priority_inversion.yaml`: Demonstrates priority inversion scenarios where low-priority tasks hold locks needed by high-priority tasks.
*   `ipc_zombie_demo.yaml`: A comprehensive process hierarchy demonstrating FORK/WAIT syscalls, Inter-Process Communication, and Zombie state management.
*   `stress_test.yaml`: High volume of concurrent processes, I/O, and memory allocations to test system limits.

## Executing an Experiment Suite

To run the full suite of experiments:

```bash
cd os-sim
source .venv/bin/activate
python experiments/runner.py
```

This will run all defined workloads against multiple algorithmic configurations (e.g., FCFS vs SJF vs RR). The raw results are saved to `reports/benchmark.json`.

## Generating Reports

After the runner completes, generate human-readable reports:

```bash
python experiments/report.py
```

This script reads `benchmark.json` and outputs:
*   `reports/benchmark.md`: A markdown summary comparing key metrics (turnaround time, page fault rate, throughput).
*   CSV files for importing into spreadsheet software for charting.

### Key Metrics Tracked

*   **Average Waiting Time**: Time spent in the READY queue.
*   **Average Turnaround Time**: Time from NEW to TERMINATED.
*   **Throughput**: Processes completed per tick.
*   **Page Fault Rate**: Ratio of page faults to total memory accesses.
*   **CPU Utilization**: Percentage of ticks the CPU was executing a process vs sitting idle.
