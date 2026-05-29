# modules/sync/monitor.py
# Phase: 7 — Synchronization & Deadlock
# Owner: Sync Agent
"""
Monitor synchronization construct wrapping a Mutex and associated Condition Variables.
Full implementation spec: OS101_AgentPlan_v2.md Section 12
"""
from __future__ import annotations

from modules.sync.mutex import Mutex


class ConditionVariable:
    """
    Condition variable associated with a specific Monitor instance.
    Allows processes to block execution until a specified condition is signaled.

    Attributes:
      monitor: Parent Monitor reference.
      wait_queue: FIFO list of PIDs blocked on this condition variable.
    """

    def __init__(self, monitor: Monitor) -> None:
        self.monitor: Monitor = monitor
        self.wait_queue: list[int] = []

    def wait(self, pid: int, tick: int = 0) -> None:
        """
        Release the parent monitor mutex lock and block the calling process.
        Appends the caller PID to the internal condition wait_queue.
        """
        self.wait_queue.append(pid)
        # Release internal monitor mutex so other processes can enter critical sections
        self.monitor.exit(pid, tick)

    def notify(self, tick: int = 0) -> int | None:
        """
        Wake up one waiting process from the head of the wait_queue.
        Returns the PID of the woken process, or None if the queue is empty.
        """
        if self.wait_queue:
            return self.wait_queue.pop(0)
        return None

    def notify_all(self, tick: int = 0) -> list[int]:
        """
        Wake up all waiting processes blocked on this condition variable.
        Returns a list of all woken PIDs.
        """
        woken_pids = list(self.wait_queue)
        self.wait_queue.clear()
        return woken_pids


class Monitor:
    """
    High-level synchronization construct encapsulating shared state, critical section access,
    and signaling variables.

    Attributes:
      monitor_id: Unique string identifier.
      mutex: Internal Mutex ensuring exclusive method execution.
      conditions: Dictionary mapping condition names to ConditionVariable instances.
    """

    def __init__(self, monitor_id: str) -> None:
        self.monitor_id: str = monitor_id
        self.mutex: Mutex = Mutex(mutex_id=f"{monitor_id}_mutex")
        self.conditions: dict[str, ConditionVariable] = {}

    def enter(self, pid: int, tick: int = 0) -> bool:
        """
        Attempt to enter the monitor by acquiring its internal mutex lock.
        Returns True if successful, False if blocked by another process.
        """
        return self.mutex.acquire(pid, tick)

    def exit(self, pid: int, tick: int = 0) -> int | None:
        """
        Exit the monitor by releasing its internal mutex lock.
        Returns the PID of a newly woken process waiting on the monitor entry mutex, or None.
        """
        return self.mutex.release(pid, tick)

    def get_condition(self, name: str) -> ConditionVariable:
        """Retrieve or instantiate a condition variable associated with this monitor."""
        if name not in self.conditions:
            self.conditions[name] = ConditionVariable(self)
        return self.conditions[name]
