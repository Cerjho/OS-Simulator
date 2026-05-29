# Architecture

OS Simulator is built with a highly decoupled, event-driven architecture designed to mimic the separation of concerns found in real operating systems.

## Component Diagram

```text
                      +-----------------------------------------+
                      |             Dashboard (React)           |
                      |   WebSockets & REST API (FastAPI)       |
                      +------------------+----------------------+
                                         |
+----------------------------------------v----------------------------------------+
|                                 core/kernel.py                                  |
| +--------------+  +--------------+  +--------------+  +--------------+          |
| |    Clock     |  |  Interrupts  |  |  Event Bus   |  |   Config     |          |
| +------+-------+  +------+-------+  +------+-------+  +------+-------+          |
+--------+-----------------+-----------------+-----------------+------------------+
         |                 |                 |                 |
         v                 v                 v                 v
+---------------------------------------------------------------------------------+
|                              Simulation Modules                                 |
|                                                                                 |
|  +-------------+    +-------------+    +-------------+    +-------------+       |
|  |   Process   |    |   Memory    |    | File System |    | I/O & Disk  |       |
|  |             |<-->|             |<-->|             |<-->|             |       |
|  | Scheduler,  |    | Allocator,  |    | FAT, inode, |    | Disk Queue, |       |
|  | PCB, Queues |    | Paging, TLB |    | VFS         |    | Devices     |       |
|  +------+------+    +-------------+    +-------------+    +------+------+       |
|         |                                                        |              |
|         +-----------------------+        +-----------------------+              |
|                                 v        v                                      |
|                             +----------------+                                  |
|                             |Synchronization |                                  |
|                             | Deadlock, Mutex|                                  |
|                             +----------------+                                  |
+---------------------------------------------------------------------------------+
```

## Tick Dispatch Order

The simulation progresses in discrete units of time called "ticks". During every tick, `kernel.py` invokes the subsystems in a strict, deterministic order. This order resolves race conditions by ensuring hardware interrupts are handled before software decisions.

| Step | Subsystem | Description |
|------|-----------|-------------|
| 1 | `InterruptController` | Handles pending hardware/software interrupts (e.g., IO_COMPLETE, TIMER). |
| 2 | `IOManager` | Advances active I/O operations and disk head movements. |
| 3 | `Scheduler` | Evaluates ready queue, preempts running process if necessary, selects next PCB. |
| 4 | `QueueManager` | Executes 1 burst unit (increments PC) for the currently running process. |
| 5 | `MemoryManager` | Handles deferred memory tasks (e.g., background page writing). |
| 6 | `VirtualFileSystem` | Processes queued file read/write operations. |
| 7 | `SyncManager` | Resolves synchronization primitives (Mutex, Semaphore waits/signals). |
| 8 | `DeadlockDetector` | Scans for circular dependencies (runs every `detection_interval` ticks). |
| 9 | `MetricsCollector` | Snapshots CPU utilization, memory usage, and throughput. |
| 10 | `EventBus` | Publishes the `TICK` event with the full system state for the dashboard. |

## Dependency Graph

To prevent circular imports and maintain strict boundaries, module dependencies follow these rules:

| Module | Imports From (Dependencies) |
|--------|------------------------------|
| `core.kernel` | `core.clock`, `core.interrupt`, `core.event_bus`, all `modules.*` |
| `modules.process.scheduler` | `modules.process.pcb`, `modules.process.queue_manager` |
| `modules.process.queue_manager` | `modules.process.pcb`, `core.interrupt`, `core.event_bus` |
| `modules.memory.paging` | `modules.memory.allocator`, `modules.memory.tlb`, `core.interrupt` |
| `modules.filesystem.vfs` | `modules.filesystem.fat`, `modules.filesystem.inode`, `core.config` |
| `modules.io.io_manager` | `modules.io.disk`, `modules.io.device`, `core.interrupt`, `core.event_bus` |
| `modules.sync.deadlock` | `core.event_bus`, `modules.sync.mutex` |

**Rule:** `modules.*` can import from `core.*`, but `core.*` (except `kernel.py`) cannot import from `modules.*`. Sibling modules (e.g., `process` and `memory`) interact purely through `Interrupts` and the `EventBus`.

## Event Catalogue

The OS Simulator `EventBus` implements the Publish/Subscribe pattern. All state changes are broadcast as events.

| Event | Source | Subscribers | Description |
|-------|--------|-------------|-------------|
| `SIMULATION_STARTED` | Kernel | Dashboard, Clock | Emitted when simulation begins. |
| `SIMULATION_STOPPED` | Kernel | Dashboard, Clock | Emitted when max ticks reached or manually stopped. |
| `SIMULATION_PAUSED` | Kernel | Dashboard | Emitted when user pauses execution. |
| `SIMULATION_RESUMED` | Kernel | Dashboard | Emitted when user resumes execution. |
| `TICK` | Kernel | Dashboard, Metrics | Broadcasts the full global state every clock tick. |
| `PROCESS_CREATED` | QueueManager | Dashboard, ProcessLog | A new PCB is instantiated. |
| `PROCESS_STATE_CHANGED`| QueueManager | Dashboard | Process moves between NEW/READY/RUNNING/BLOCKED. |
| `PROCESS_TERMINATED` | QueueManager | Dashboard, Metrics | Process completes its final burst. |
| `CONTEXT_SWITCH` | QueueManager | Scheduler, Dashboard | CPU control is handed to a new process. |
| `PAGE_FAULT` | Paging | Metrics | A virtual address translation failed in TLB and Page Table. |
| `FRAME_ALLOCATED` | Allocator | Dashboard | Physical memory frame is reserved. |
| `IO_REQUESTED` | IOManager | DiskScheduler | Process requests a disk or device read/write. |
| `IO_COMPLETED` | IOManager | InterruptController | Device finishes operation; raises interrupt to unblock process. |
| `DISK_SEEK` | DiskScheduler| Dashboard | Disk arm moves from one cylinder to another. |
| `RESOURCE_ACQUIRED` | SyncManager | DeadlockDetector | A process successfully locks a Mutex/Semaphore. |
| `RESOURCE_RELEASED` | SyncManager | DeadlockDetector | A process frees a Mutex/Semaphore. |
| `DEADLOCK_DETECTED` | Deadlock | Dashboard, Log | Circular wait cycle identified in Resource Allocation Graph. |
| `RECOVERY_EXECUTED` | Deadlock | QueueManager | Processes are forcibly terminated/preempted to break deadlock. |
