# modules/sync/mutex.py
# Phase: 7 — Synchronization & Deadlock
# Owner: Sync Agent
"""
Mutex synchronization primitive implementation.
Enforces non-reentrant ownership and block/wakeup invariants.
Full implementation spec: OS101_AgentPlan_v2.md Section 12
"""
from __future__ import annotations


class DeadlockWarning(Warning):
    """Raised when a process attempts to acquire a mutex it already owns (re-entrant deadlock)."""
    pass


class Mutex:
    """
    Mutual exclusion lock ensuring single-process critical section access.

    Attributes:
      mutex_id: Unique string identifier.
      locked: Boolean indicating if the mutex is currently held.
      owner_pid: Process ID of the lock holder, or None if unlocked.
      wait_queue: FIFO list of PIDs blocked awaiting lock acquisition.
    """

    def __init__(self, mutex_id: str) -> None:
        self.mutex_id: str = mutex_id
        self.locked: bool = False
        self.owner_pid: int | None = None
        self.wait_queue: list[int] = []

    def _check_invariants(self) -> None:
        """Enforce strict structural integrity invariants required by implementation specs."""
        assert (self.owner_pid is None) == (not self.locked), (
            f"Mutex {self.mutex_id} invariant failed: owner_pid ({self.owner_pid}) "
            f"is None ↔ locked ({self.locked}) is False"
        )
        assert self.owner_pid not in self.wait_queue, (
            f"Mutex {self.mutex_id} invariant failed: owner_pid ({self.owner_pid}) "
            f"must not be present in wait_queue {self.wait_queue}"
        )

    def acquire(self, pid: int, tick: int = 0) -> bool:
        """
        Attempt to acquire the mutex lock.

        Returns:
          True if successfully acquired.
          False if locked by another process (caller blocks and is appended to wait_queue).

        Raises:
          DeadlockWarning if already locked by the requested pid.
        """
        try:
            if not self.locked:
                self.locked = True
                self.owner_pid = pid
                return True

            if self.owner_pid == pid:
                raise DeadlockWarning(f"Process {pid} attempted to re-acquire mutex {self.mutex_id}")

            self.wait_queue.append(pid)
            return False
        finally:
            self._check_invariants()

    def release(self, pid: int, tick: int = 0) -> int | None:
        """
        Release the mutex lock.

        Returns:
          Process ID of the newly woken owner if wait_queue was non-empty.
          None if wait_queue was empty.

        Raises:
          PermissionError if requested pid does not hold the lock.
        """
        try:
            if self.owner_pid != pid:
                raise PermissionError(
                    f"Process {pid} does not own mutex {self.mutex_id} (owned by {self.owner_pid})"
                )

            if self.wait_queue:
                # Transfer ownership directly to the head of the wait queue
                next_owner = self.wait_queue.pop(0)
                self.owner_pid = next_owner
                self.locked = True
                return next_owner

            self.locked = False
            self.owner_pid = None
            return None
        finally:
            self._check_invariants()

    def try_acquire(self, pid: int) -> bool:
        """
        Non-blocking acquisition attempt.
        Returns True if acquired, False if currently held by another process.
        """
        try:
            if not self.locked:
                self.locked = True
                self.owner_pid = pid
                return True

            if self.owner_pid == pid:
                raise DeadlockWarning(f"Process {pid} attempted to re-acquire mutex {self.mutex_id}")

            return False
        finally:
            self._check_invariants()
