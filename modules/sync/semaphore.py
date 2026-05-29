# modules/sync/semaphore.py
# Phase: 7 — Synchronization & Deadlock
# Owner: Sync Agent
"""
Counting and Binary Semaphore synchronization primitives.
Full implementation spec: OS101_AgentPlan_v2.md Section 12
"""
from __future__ import annotations


class Semaphore:
    """
    Counting semaphore allowing multi-unit resource allocation.
    When value goes negative, its absolute magnitude represents the number of blocked processes.

    Attributes:
      value: Current integer resource count (can be negative).
      wait_queue: FIFO list of PIDs blocked awaiting availability.
    """

    def __init__(self, initial_value: int) -> None:
        if initial_value < 0:
            raise ValueError(f"Semaphore initial_value cannot be negative (got {initial_value})")
        self.value: int = initial_value
        self.wait_queue: list[int] = []

    def wait(self, pid: int, tick: int = 0) -> bool:
        """
        P (Proberen) / wait operation. Decrements semaphore value.

        Returns:
          True if resource is allocated immediately (caller continues).
          False if resource unavailable (caller blocks and is added to wait_queue).
        """
        self.value -= 1
        if self.value < 0:
            self.wait_queue.append(pid)
            return False
        return True

    def signal(self, pid: int, tick: int = 0) -> int | None:
        """
        V (Verhogen) / signal operation. Increments semaphore value.

        Returns:
          Process ID of the first waiting process woken up (caller must unblock it).
          None if wait_queue was empty.
        """
        self.value += 1
        if self.wait_queue:
            return self.wait_queue.pop(0)
        return None


class BinarySemaphore(Semaphore):
    """
    Binary semaphore optimized for mutual exclusion with a strict ceiling of 1.
    """

    def __init__(self) -> None:
        super().__init__(initial_value=1)

    def signal(self, pid: int, tick: int = 0) -> int | None:
        """
        V / signal operation enforcing ceiling limit.
        Raises ValueError if signaling would exceed the binary capacity of 1.
        """
        if self.value >= 1:
            raise ValueError("BinarySemaphore ceiling exceeded: cannot signal when value is already 1")
        return super().signal(pid, tick)
