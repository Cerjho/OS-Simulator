# OS Simulator

A comprehensive operating system simulation built for educational exploration of core OS concepts including process scheduling, memory management, file systems, I/O device management, and synchronization primitives. Designed as an interactive laboratory for studying textbook algorithms with real-time visualization.

## Quick Start

### Using the CLI launcher (recommended)

```bash
cd os-sim
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
python sim_launcher.py start
```

This starts both the backend (`localhost:8000`) and the dashboard (`localhost:5173`).
Press **Ctrl+C** to stop all services.

Other useful commands:

```bash
python sim_launcher.py setup     # Run first-time setup wizard
python sim_launcher.py all       # Run tests first, then launch if passing
python sim_launcher.py docs      # Serve the documentation site (localhost:8080)
python sim_launcher.py test      # Run all unit tests with coverage
python sim_launcher.py check     # Quick pass/fail health check
python sim_launcher.py --help    # Show all commands and options
```

### Manual launch (alternative)

```bash
cd os-sim
# Activate your venv (see above), then:
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload &
cd dashboard && npm run dev
```

Open `http://localhost:5173` to access the real-time dashboard.

## What This Simulates

| Subsystem | What It Does |
|-----------|-------------|
| **CPU Scheduling** | FCFS, SJF, SRTF, Priority, Round Robin, MLFQ with preemption, aging, and Gantt chart logging |
| **Memory Management** | Physical frame allocation (first-fit, best-fit, worst-fit), demand paging with LRU/FIFO/Clock/Optimal replacement, TLB simulation |
| **File Systems** | FAT and inode-based filesystems with VFS abstraction, directory trees, hard/symbolic links |
| **I/O & Disk** | 6 disk scheduling algorithms (FCFS, SSTF, SCAN, C-SCAN, LOOK, C-LOOK) with seek distance tracking |
| **Synchronization** | Mutex, counting/binary semaphores, monitors, deadlock detection via RAG cycle analysis, Banker's Algorithm |
| **Dashboard** | React-based real-time UI with WebSocket push, Gantt charts, memory maps, and disk arm visualization |

## Architecture Overview

```
┌──────────────────────────────────────────────┐
│                  Dashboard (React)            │
│       WebSocket ◄──── /api/ws/realtime        │
├──────────────────────────────────────────────┤
│          FastAPI Backend (api/)               │
│    /control   /state   /config               │
├──────────────────────────────────────────────┤
│              core/kernel.py                   │
│    Clock → Scheduler → Memory → FS → IO      │
├──────────────────────────────────────────────┤
│              Simulation Modules               │
│  process/  memory/  filesystem/  io/  sync/   │
└──────────────────────────────────────────────┘
```

## Running Tests

```bash
# Run all 161 tests
python -m pytest tests/ -v

# Run with coverage report
python -m pytest tests/ --cov=core --cov=modules --cov-report=html

# Run specific test module
python -m pytest tests/unit/test_scheduler_fcfs.py -v
```

## Running Experiments

### Evaluation Preset Workloads

The simulator includes 8 built-in evaluation preset workloads that configure the OS for specific scenarios (e.g., deadlock demonstration, memory pressure, I/O heavy). You can run them directly from the dashboard UI via the **Control Panel**.

### CLI Benchmarks

```bash
# Run all benchmark experiments
python experiments/runner.py

# Generate markdown report from results
python experiments/report.py

# View results
cat reports/benchmark.md
```

## Configuration

All simulation parameters are controlled via `simulation.yaml`:

```yaml
clock:
  tick_rate_ms: 100
  max_ticks: 10000

scheduler:
  algorithm: round_robin   # fcfs | sjf | srtf | priority | round_robin | mlfq
  time_quantum: 4
  preemptive: true

memory:
  total_frames: 64
  algorithm: lru           # fifo | lru | optimal | clock
  tlb_size: 16

disk:
  scheduling: sstf         # fcfs | sstf | scan | c-scan | look | c-look
  cylinders: 200
  initial_head: 53
```

See [Configuration Reference](docs/user-guide/config-ref.md) for the full list of 27 configurable parameters.

## Known Limitations

1. **Not a real kernel** — This is a user-space simulation. It does not interact with actual hardware, system calls, or CPU privilege rings. All "processes" are simulated data structures.

2. **Not multi-core** — The simulation models a single-CPU system. There is no support for SMP scheduling, per-core run queues, or cache coherence protocols.

3. **Not networked** — No network stack, socket abstraction, or distributed systems communication is simulated. All operations are local to the simulation process.

4. **Not persistent across restarts** — All simulation state (processes, file system contents, memory mappings) exists only in memory. Restarting the backend resets everything to the initial configuration.

5. **No security/access control** — There are no user accounts, file permissions enforcement, capability systems, or address space isolation. All simulated processes have unrestricted access to all resources.

## License

Educational use. See `OS101_AgentPlan_v2.md` for full project specification.
