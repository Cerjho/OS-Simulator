# Dashboard Guide

The OS Simulator Dashboard is a real-time, interactive React application that visualizes the internal state of the simulated operating system. It connects to the FastAPI backend via WebSockets to receive `TICK` events.

## Layout Overview

The dashboard is divided into several key panels:

### 1. Control Panel
Located at the top, this panel controls the simulation clock.
*   **Start**: Begins or resumes the simulation.
*   **Pause**: Halts the clock. You can inspect the current state without it changing.
*   **Stop**: Halts the clock and resets the simulation to tick 0, clearing all queues and memory.
*   **Tick Counter**: Displays the current absolute simulation time.

### 2. CPU & Process Queues
Displays the state of the Process Manager.
*   **Gantt Chart**: A visual timeline of which process was on the CPU at any given tick. Colors are deterministic per PID.
*   **Queues**: Shows lists of PCBs currently in the `NEW`, `READY`, `RUNNING`, and `BLOCKED` states.
*   **Metrics**: Live calculation of CPU utilization and total context switches.

### 3. Memory Map
Visualizes the physical RAM (frames) and Virtual Memory (pages).
*   **Frame Grid**: Each block represents a physical frame. Colors indicate which process owns the frame. Empty blocks are free space.
*   **TLB**: Shows the current entries in the Translation Lookaside Buffer.
*   **Metrics**: Displays the current page fault rate and TLB hit rate.

### 4. Disk & I/O
Visualizes the disk scheduler and pending I/O requests.
*   **Disk Arm**: An animated slider showing the current position of the read/write head across the cylinders.
*   **Pending Requests**: The queue of I/O operations waiting to be serviced.

### 5. Synchronization & Deadlock
Monitors the state of Mutexes and the Deadlock Detector.
*   **Resource Allocation Graph (RAG)**: A text/visual representation of which processes hold which resources, and which are waiting.
*   **Deadlock Alerts**: If the Banker's Algorithm or cycle detector finds a deadlock, an alert flashes here showing the affected PIDs.

## Dynamic Configuration

You do not need to restart the backend to change algorithms. Use the **Config Tab** in the dashboard to modify settings like the Scheduling Algorithm or Page Replacement strategy. The changes take effect immediately on the next tick.
