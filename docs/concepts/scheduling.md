# CPU Scheduling

CPU scheduling determines which process in the ready queue is allocated the CPU. The objective is to maximize CPU utilization, throughput, and fairness while minimizing waiting time, turnaround time, and response time.

## Algorithms

**First-Come, First-Served (FCFS)**
The simplest scheduling algorithm. Processes are assigned the CPU in the exact order they arrive in the ready queue. It is non-preemptive. While easy to implement, it suffers from the "convoy effect" where short processes get stuck waiting behind long processes, leading to high average waiting times.

**Shortest Job First (SJF)**
This algorithm associates with each process the length of its next CPU burst. When the CPU is available, it is assigned to the process with the smallest next CPU burst. It provides the provably optimal minimum average waiting time. However, it requires knowing the future burst length, which is practically impossible, so it is often approximated using exponential averaging of past bursts.

**Shortest Remaining Time First (SRTF)**
The preemptive version of SJF. If a new process arrives with a CPU burst length shorter than what is remaining of the currently executing process, the current process is preempted. This provides even better responsiveness for short tasks but increases context switching overhead.

**Priority Scheduling**
Each process is assigned a priority integer. The CPU is allocated to the process with the highest priority (in OS Simulator, lower numbers represent higher priority). It can be preemptive or non-preemptive. A major problem is indefinite blocking (starvation), where low-priority processes never execute. The solution is *aging* — gradually increasing the priority of processes that wait in the system for a long time.

**Round Robin (RR)**
Designed specifically for time-sharing systems. It is similar to FCFS, but preemption is added. A small unit of time, called a time quantum or time slice, is defined. The ready queue is treated as a circular queue. The scheduler goes around the ready queue, allocating the CPU to each process for a time interval of up to one time quantum. It guarantees fairness and excellent response time.

**Multilevel Feedback Queue (MLFQ)**
The most complex and adaptable algorithm. It separates processes into multiple queues based on their CPU burst behavior. If a process uses too much CPU time, it is moved to a lower-priority queue (demotion). This leaves I/O-bound and interactive processes in the higher-priority queues. To prevent starvation, processes that wait too long in a lower queue are moved back to a higher queue (aging).

## Comparison

| Algorithm | Preemptive | Selection Criterion | Starvation Risk | Best For |
|-----------|------------|---------------------|-----------------|----------|
| **FCFS** | No | Arrival time | No | Batch systems with predictable loads |
| **SJF** | No | Shortest burst | Yes | Minimizing average wait time |
| **SRTF** | Yes | Shortest remaining burst | Yes | Highly responsive batch systems |
| **Priority** | Both | Priority value | **Yes** | Systems with strict hierarchical importance |
| **Round Robin** | Yes | Arrival time + Quantum | No | Time-sharing, interactive systems |
| **MLFQ** | Yes | History + Queue level | Prevented via aging | General purpose operating systems |

## Workload Examples

Consider the following verified textbook workload:
*   **P1**: burst = 10, arrival = 0
*   **P2**: burst = 5, arrival = 0
*   **P3**: burst = 8, arrival = 0

### FCFS Gantt Chart
Since they all arrive at 0, they execute in PID order without interruption.

`| P1 [0-10] | P2 [10-15] | P3 [15-23] |`

*   **Average Waiting Time:** (0 + 10 + 15) / 3 = 8.33

### Round Robin (q=3) Gantt Chart
Each process gets exactly 3 ticks before being preempted and placed at the back of the queue. P2 finishes early in its second slice.

`| P1 [0-3] | P2 [3-6] | P3 [6-9] | P1 [9-12] | P2 [12-14] (finishes) | P3 [14-17] | P1 [17-20] | P3 [20-22] (finishes) | P1 [22-23] (finishes) |`

*   **Average Waiting Time:** P1 waits (0 + 6 + 5 + 2 = 13), P2 waits (3 + 6 = 9), P3 waits (6 + 5 + 3 = 14). Avg: (13 + 9 + 14) / 3 = 12.0
