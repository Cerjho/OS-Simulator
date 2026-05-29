# OS Simulator

Welcome to the documentation for the OS Simulator, an educational operating system simulator designed to help you understand the core concepts of operating systems through interactive visualization and experimentation.

## What is OS Simulator?

OS Simulator is a modular, event-driven simulation that models the key subsystems of a modern operating system:

*   **Process Management & CPU Scheduling**: Simulate FCFS, SJF, SRTF, Priority, Round Robin, and MLFQ algorithms.
*   **Memory Management**: Explore physical contiguous allocation (first-fit, best-fit, worst-fit) and demand paging (FIFO, LRU, Clock, Optimal) with a TLB.
*   **File Systems**: Compare FAT and inode-based file system structures and performance.
*   **I/O Management**: Analyze disk seek algorithms (FCFS, SSTF, SCAN, C-SCAN, LOOK, C-LOOK).
*   **Synchronization**: Investigate race conditions, mutexes, semaphores, monitors, and deadlock detection/recovery (Banker's Algorithm).

## How to Use This Documentation

*   **[Getting Started](getting-started.md)**: Set up the simulator, run the backend API, and start the frontend dashboard.
*   **[Architecture](architecture.md)**: Understand the internal structure, tick cycle, and event bus of the simulator.
*   **User Guide**: Learn how to use the interactive [Dashboard](user-guide/dashboard.md), run automated [Experiments](user-guide/experiments.md), and tweak settings in the [Config Reference](user-guide/config-ref.md).
*   **Concepts**: Dive deep into the theory behind [CPU Scheduling](concepts/scheduling.md), [Memory](concepts/memory.md), [File Systems](concepts/filesystem.md), [I/O](concepts/io.md), and [Synchronization](concepts/sync.md).
