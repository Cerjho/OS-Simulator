# Synchronization & Deadlock

In a multiprogramming environment, multiple processes concurrently executing and sharing resources can lead to race conditions. OS Simulator implements several synchronization primitives to enforce mutual exclusion and manage shared state.

## Primitives Comparison

| Primitive | Mechanism | Best For |
|-----------|-----------|----------|
| **Mutex (Mutual Exclusion)** | A simple lock. Only the process that acquired the lock can release it. Trying to lock an already locked mutex blocks the caller. | Protecting critical sections of code that only one process can enter at a time. |
| **Semaphore (Counting)** | An integer value representing available permits, with atomic `wait()` and `signal()` operations. | Managing pools of identical resources (e.g., 3 printers). |
| **Semaphore (Binary)** | A semaphore restricted to values 0 and 1. Similar to a mutex, but allows *any* process to signal/release it. | General signaling between processes, or priority inheritance protocols. |
| **Monitor** | A high-level abstraction (often built into languages like Java) that encapsulates shared variables and procedures, implicitly enforcing mutual exclusion. | Building robust thread-safe data structures like Bounded Buffers. |

## Deadlocks

A deadlock is a system state where a set of processes are blocked because each process is holding a resource and waiting for another resource acquired by some other process.

### The Coffman Conditions
For a deadlock to exist, four conditions must hold simultaneously:

1.  **Mutual Exclusion**: At least one resource must be held in a non-sharable mode. *(Example: A mutex lock).*
2.  **Hold and Wait**: A process must be holding at least one resource and waiting to acquire additional resources held by other processes. *(Example: Holding lock A, requesting lock B).*
3.  **No Preemption**: Resources cannot be preempted; a resource can be released only voluntarily by the process holding it. *(Example: You cannot forcibly rip a lock away from a process).*
4.  **Circular Wait**: A closed chain of processes exists, where each process holds at least one resource needed by the next process in the chain.

## Banker's Algorithm (Deadlock Avoidance)

The Banker's Algorithm avoids deadlock by simulating resource allocation for every request. It only grants requests if the resulting state is "Safe" — meaning there exists at least one sequence where all processes can finish.

### Safe State Example (Section 18.5)
Consider a system with 5 processes (P0-P4) and 3 resource types (A, B, C):

**Available Vector:** `A: 3, B: 3, C: 2`

**Need Matrix:**
| Process | A | B | C |
|---------|---|---|---|
| **P0** | 7 | 4 | 3 |
| **P1** | 1 | 2 | 2 |
| **P2** | 6 | 0 | 0 |
| **P3** | 0 | 1 | 1 |
| **P4** | 4 | 3 | 1 |

*Is this state safe? Yes.*
1. **P1**'s needs (1,2,2) <= Available (3,3,2). P1 runs and releases its allocated resources.
2. New Available: `(5, 3, 2)`
3. **P3**'s needs (0,1,1) <= Available (5,3,2). P3 runs and releases.
4. New Available: `(7, 4, 3)`
5. **P4**'s needs (4,3,1) <= Available (7,4,3). P4 runs and releases.
6. New Available: `(7, 4, 5)`
7. **P0**'s needs (7,4,3) <= Available (7,4,5). P0 runs and releases.
8. New Available: `(7, 5, 5)`
9. **P2**'s needs (6,0,0) <= Available (7,5,5). P2 runs.

**Safe Sequence:** `< P1, P3, P4, P0, P2 >`

## Deadlock Detection: The Dining Philosophers

When deadlock avoidance is too expensive, OS Simulator uses a Deadlock Detector that periodically scans the Resource Allocation Graph (RAG) for cycles.

The classic Dining Philosophers problem demonstrates this: 5 philosophers sit at a table with 5 forks. To eat, they need both the left and right fork. If all 5 pick up their left fork simultaneously, the system deadlocks.

### RAG Cycle Diagram

```ascii
     [Fork 0] ◄──────── (Philosopher 0) ◄──────── [Fork 4]
        │                                            ▲
        ▼                                            │
 (Philosopher 1)                              (Philosopher 4)
        │                                            ▲
        ▼                                            │
     [Fork 1]                                     [Fork 3]
        │                                            ▲
        ▼                                            │
 (Philosopher 2) ────────► [Fork 2] ────────► (Philosopher 3)

Legend:
(Process) ──► [Resource] = Request Edge (Waiting)
[Resource] ──► (Process) = Assignment Edge (Holding)
```
OS Simulator detects this cycle and executes a recovery strategy (e.g., terminating the youngest philosopher) to break the chain.
