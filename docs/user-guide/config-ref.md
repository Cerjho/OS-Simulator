# Configuration Reference

The behavior of the OS Simulator simulation is controlled entirely by `simulation.yaml`. This file defines the hardware parameters, algorithms, and simulation limits.

## Clock Settings

| Key | Type | Default | Valid Values | Description |
|-----|------|---------|--------------|-------------|
| `clock.tick_rate_ms` | `int` | `100` | `> 0` | Real-world milliseconds between simulation ticks. |
| `clock.max_ticks` | `int` | `10000` | `> 0` | Automatic stop point for the simulation. |
| `clock.auto_start` | `bool` | `False` | `True`, `False` | If true, clock starts ticking immediately on boot. |

## CPU Settings

| Key | Type | Default | Valid Values | Description |
|-----|------|---------|--------------|-------------|
| `cpu.cores` | `int` | `1` | `1` | Number of CPU cores. (Note: Multi-core is currently unsupported). |
| `cpu.context_switch_cost` | `int` | `2` | `>= 0` | Ticks required to perform a context switch. |

## Scheduler Settings

| Key | Type | Default | Valid Values | Description |
|-----|------|---------|--------------|-------------|
| `scheduler.algorithm` | `str` | `"round_robin"` | `"fcfs"`, `"sjf"`, `"srtf"`, `"priority"`, `"round_robin"`, `"mlfq"` | The CPU scheduling algorithm. |
| `scheduler.time_quantum` | `int` | `4` | `> 0` | Time slice duration for RR and MLFQ. |
| `scheduler.preemptive` | `bool` | `True` | `True`, `False` | Whether high-priority arrivals can interrupt running processes. |
| `scheduler.aging_interval` | `int` | `50` | `> 0` | Ticks before a process receives a priority boost (prevents starvation). |

## Memory Settings

| Key | Type | Default | Valid Values | Description |
|-----|------|---------|--------------|-------------|
| `memory.total_frames` | `int` | `64` | `> 0` | Total number of physical memory frames available. |
| `memory.page_size_kb` | `int` | `4` | `> 0` | Size of a single page/frame in kilobytes. |
| `memory.algorithm` | `str` | `"lru"` | `"fifo"`, `"lru"`, `"optimal"`, `"clock"` | Page replacement algorithm used during demand paging. |
| `memory.swap_enabled` | `bool` | `True` | `True`, `False` | Allows pages to be evicted to disk when memory is full. |
| `memory.tlb_size` | `int` | `16` | `>= 0` | Number of entries in the Translation Lookaside Buffer. |

## Filesystem Settings

| Key | Type | Default | Valid Values | Description |
|-----|------|---------|--------------|-------------|
| `filesystem.type` | `str` | `"fat"` | `"fat"`, `"inode"` | The underlying filesystem architecture. |
| `filesystem.total_blocks` | `int` | `512` | `> 0` | Total storage blocks available. |
| `filesystem.block_size_kb` | `int` | `4` | `> 0` | Size of a single storage block in kilobytes. |

## Disk Settings

| Key | Type | Default | Valid Values | Description |
|-----|------|---------|--------------|-------------|
| `disk.scheduling` | `str` | `"sstf"` | `"fcfs"`, `"sstf"`, `"scan"`, `"c-scan"`, `"look"`, `"c-look"` | Disk arm scheduling algorithm. |
| `disk.cylinders` | `int` | `200` | `> 0` | Total number of tracks/cylinders on the disk. |
| `disk.initial_head` | `int` | `53` | `0` to `cylinders - 1` | Starting cylinder position of the disk arm. |
| `disk.seek_time_per_track`| `int` | `1` | `>= 0` | Ticks cost per cylinder seek distance. |

## Process Generation Settings

| Key | Type | Default | Valid Values | Description |
|-----|------|---------|--------------|-------------|
| `processes.initial_load` | `int` | `5` | `>= 0` | Number of random processes generated at tick 0. |
| `processes.auto_spawn` | `bool` | `True` | `True`, `False` | Enable random background process generation over time. |
| `processes.spawn_interval_ticks`| `int` | `20` | `> 0` | Average interval between auto-spawning new processes. |

## Deadlock Settings

| Key | Type | Default | Valid Values | Description |
|-----|------|---------|--------------|-------------|
| `deadlock.detection_interval` | `int` | `10` | `> 0` | Frequency (in ticks) to run cycle detection on the RAG. |
| `deadlock.recovery_strategy`| `str` | `"terminate_youngest"`| `"terminate_youngest"`, `"terminate_lowest"`, `"resource_preempt"` | Strategy used to break detected deadlocks. |

## Logging Settings

| Key | Type | Default | Valid Values | Description |
|-----|------|---------|--------------|-------------|
| `logging.level` | `str` | `"INFO"` | `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"` | Console logging verbosity. |
| `logging.log_to_file` | `bool` | `True` | `True`, `False` | Write logs to disk. |
| `logging.log_path` | `str` | `"logs/simulation.log"` | Any path | Filepath for disk logging. |
