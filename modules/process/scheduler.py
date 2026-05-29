# modules/process/scheduler.py
# Phase: 6 — Scheduling Algorithm Lab
# Owner: Scheduler Agent
"""
CPU Scheduling algorithms implementation.
Supports FCFS, SJF, SRTF, Priority, Round Robin, and MLFQ.
Full implementation spec: OS101_AgentPlan_v2.md Section 11
"""
from __future__ import annotations
from typing import Protocol, runtime_checkable, TYPE_CHECKING

from core.interrupt import InterruptType

if TYPE_CHECKING:
    from core.config import SchedulerConfig
    from modules.process.pcb import PCB
    from modules.process.queue_manager import QueueManager


@runtime_checkable
class SchedulerAlgorithm(Protocol):
    """Protocol defining the interface for all CPU scheduling algorithms."""

    def select_next(self, ready_queue: list[PCB], tick: int) -> PCB | None:
        """Choose the next process to run from ready_queue without modifying state."""
        ...

    def should_preempt(self, running: PCB, ready_queue: list[PCB], tick: int) -> bool:
        """Return True if the running process should be preempted."""
        ...

    def tick(self, tick: int, queue_manager: QueueManager) -> None:
        """Invoked each clock tick to manage preemption, aging, and dispatching."""
        ...


# ── 1. First-Come, First-Served (FCFS) ────────────────────────────────────────

class FCFS:
    """Non-preemptive First-Come, First-Served scheduler."""

    def __init__(self, config: SchedulerConfig) -> None:
        self.config: SchedulerConfig = config

    def select_next(self, ready_queue: list[PCB], tick: int) -> PCB | None:
        if not ready_queue:
            return None
        # Selection: smallest arrival_time; tie → smallest pid
        return min(ready_queue, key=lambda p: (p.arrival_time, p.pid))

    def should_preempt(self, running: PCB, ready_queue: list[PCB], tick: int) -> bool:
        return False

    def tick(self, tick: int, queue_manager: QueueManager) -> None:
        # Dispatch next process only when CPU is idle
        if queue_manager.running is None and queue_manager.ready_queue:
            next_pcb = self.select_next(queue_manager.ready_queue, tick)
            if next_pcb is not None:
                queue_manager.dispatch(next_pcb, tick)


# ── 2. Shortest Job First (SJF) ───────────────────────────────────────────────

class SJF:
    """Non-preemptive Shortest Job First scheduler."""

    def __init__(self, config: SchedulerConfig) -> None:
        self.config: SchedulerConfig = config

    def select_next(self, ready_queue: list[PCB], tick: int) -> PCB | None:
        if not ready_queue:
            return None
        # BUG-21 fix: Use remaining_burst instead of burst_time for correct selection
        # after I/O unblock or preemption, remaining_burst reflects actual work left
        return min(ready_queue, key=lambda p: (p.remaining_burst, p.arrival_time, p.pid))

    def should_preempt(self, running: PCB, ready_queue: list[PCB], tick: int) -> bool:
        return False

    def tick(self, tick: int, queue_manager: QueueManager) -> None:
        # Dispatch only when CPU is idle
        if queue_manager.running is None and queue_manager.ready_queue:
            next_pcb = self.select_next(queue_manager.ready_queue, tick)
            if next_pcb is not None:
                queue_manager.dispatch(next_pcb, tick)


# ── 3. Shortest Remaining Time First (SRTF) ───────────────────────────────────

class SRTF:
    """Preemptive Shortest Remaining Time First scheduler."""

    def __init__(self, config: SchedulerConfig) -> None:
        self.config: SchedulerConfig = config

    def select_next(self, ready_queue: list[PCB], tick: int) -> PCB | None:
        if not ready_queue:
            return None
        # Selection: smallest remaining_burst
        return min(ready_queue, key=lambda p: (p.remaining_burst, p.arrival_time, p.pid))

    def should_preempt(self, running: PCB, ready_queue: list[PCB], tick: int) -> bool:
        if not ready_queue:
            return False
        best_ready = min(ready_queue, key=lambda p: p.remaining_burst)
        return best_ready.remaining_burst < running.remaining_burst

    def tick(self, tick: int, queue_manager: QueueManager) -> None:
        # Check preemption if a process is running
        if queue_manager.running is not None:
            if self.should_preempt(queue_manager.running, queue_manager.ready_queue, tick):
                queue_manager.preempt(tick)

        # Dispatch next process if CPU is idle
        if queue_manager.running is None and queue_manager.ready_queue:
            next_pcb = self.select_next(queue_manager.ready_queue, tick)
            if next_pcb is not None:
                queue_manager.dispatch(next_pcb, tick)


# ── 4. Priority Scheduler ─────────────────────────────────────────────────────

class PriorityScheduler:
    """Priority scheduler supporting optional preemption and aging."""

    def __init__(self, config: SchedulerConfig) -> None:
        self.config: SchedulerConfig = config

    def select_next(self, ready_queue: list[PCB], tick: int) -> PCB | None:
        if not ready_queue:
            return None
        # Selection: smallest priority number (0=highest); tie → smallest arrival_time
        return min(ready_queue, key=lambda p: (p.priority, p.arrival_time, p.pid))

    def should_preempt(self, running: PCB, ready_queue: list[PCB], tick: int) -> bool:
        if not self.config.preemptive or not ready_queue:
            return False
        best_ready = min(ready_queue, key=lambda p: p.priority)
        return best_ready.priority < running.priority

    def _apply_aging(self, ready_queue: list[PCB], tick: int) -> None:
        """Increment priority (decrease number) of all ready processes to prevent starvation.
        BUG-34 fix: never go below 0, and original_priority is preserved on PCB for reference."""
        for pcb in ready_queue:
            if pcb.priority > 0:
                pcb.priority -= 1

    def tick(self, tick: int, queue_manager: QueueManager) -> None:
        # Apply aging periodically
        if tick > 0 and tick % self.config.aging_interval == 0:
            self._apply_aging(queue_manager.ready_queue, tick)

        # Check preemption
        if queue_manager.running is not None:
            if self.should_preempt(queue_manager.running, queue_manager.ready_queue, tick):
                queue_manager.preempt(tick)

        # Dispatch if idle
        if queue_manager.running is None and queue_manager.ready_queue:
            next_pcb = self.select_next(queue_manager.ready_queue, tick)
            if next_pcb is not None:
                queue_manager.dispatch(next_pcb, tick)


# ── 5. Round Robin (RR) ───────────────────────────────────────────────────────

class RoundRobin:
    """Preemptive Round Robin scheduler using time quanta."""

    def __init__(self, config: SchedulerConfig) -> None:
        self.config: SchedulerConfig = config

    def select_next(self, ready_queue: list[PCB], tick: int) -> PCB | None:
        if not ready_queue:
            return None
        # FIFO order: ready_queue natively functions as circular queue
        return ready_queue[0]

    def should_preempt(self, running: PCB, ready_queue: list[PCB], tick: int) -> bool:
        return running.time_slice_used >= self.config.time_quantum

    def tick(self, tick: int, queue_manager: QueueManager) -> None:
        running = queue_manager.running
        if running is not None:
            # Check if time quantum exceeded
            if self.should_preempt(running, queue_manager.ready_queue, tick):
                # BUG-33 fix: Do NOT raise TIMER interrupt here — it would be handled
                # at the NEXT tick, double-preempting the newly dispatched process.
                # Preempt directly; dispatch() resets time_slice_used.
                queue_manager.preempt(tick)

        # Dispatch next process if CPU is idle
        if queue_manager.running is None and queue_manager.ready_queue:
            next_pcb = self.select_next(queue_manager.ready_queue, tick)
            if next_pcb is not None:
                queue_manager.dispatch(next_pcb, tick)


# ── 6. Multi-Level Feedback Queue (MLFQ) ──────────────────────────────────────

class MLFQ:
    """
    Multi-Level Feedback Queue scheduler.
    Level 0: RR (quantum = time_quantum)
    Level 1: RR (quantum = time_quantum * 2)
    Level 2: FCFS
    """

    def __init__(self, config: SchedulerConfig) -> None:
        self.config: SchedulerConfig = config

    def admit(self, pcb: PCB) -> None:
        """New processes enter queue level 0."""
        pcb.mlfq_queue_level = 0

    def on_full_quantum_used(self, pcb: PCB) -> None:
        """Demote process to a lower priority queue level upon exhausting its quantum."""
        if pcb.mlfq_queue_level < 2:
            pcb.mlfq_queue_level += 1

    def select_next(self, ready_queue: list[PCB], tick: int) -> PCB | None:
        # Selection priority: level 0 first, then 1, then 2
        level0 = [p for p in ready_queue if p.mlfq_queue_level == 0]
        if level0:
            return level0[0]

        level1 = [p for p in ready_queue if p.mlfq_queue_level == 1]
        if level1:
            return level1[0]

        level2 = [p for p in ready_queue if p.mlfq_queue_level == 2]
        if level2:
            return min(level2, key=lambda p: (p.arrival_time, p.pid))

        return None

    def should_preempt(self, running: PCB, ready_queue: list[PCB], tick: int) -> bool:
        # Immediate preemption if a new process arrives at level 0 while running is at level 1 or 2
        if running.mlfq_queue_level > 0:
            if any(p.mlfq_queue_level == 0 for p in ready_queue):
                return True

        # Quantum expiration preemption checks
        if running.mlfq_queue_level == 0:
            return running.time_slice_used >= self.config.time_quantum
        elif running.mlfq_queue_level == 1:
            return running.time_slice_used >= (self.config.time_quantum * 2)

        return False

    def tick(self, tick: int, queue_manager: QueueManager) -> None:
        # Apply Promotion/Aging periodically
        if tick > 0 and tick % self.config.aging_interval == 0:
            # Promote all processes in ready queue and running state
            for pcb in queue_manager.ready_queue:
                if pcb.mlfq_queue_level > 0:
                    pcb.mlfq_queue_level -= 1
            if queue_manager.running is not None and queue_manager.running.mlfq_queue_level > 0:
                queue_manager.running.mlfq_queue_level -= 1
                # BUG-22 fix: Reset time_slice when promoting running process to
                # prevent immediate preemption due to accumulated slice from old level
                queue_manager.running.time_slice_used = 0

        running = queue_manager.running
        if running is not None:
            if self.should_preempt(running, queue_manager.ready_queue, tick):
                # Determine if preemption is due to quantum exhaustion or higher-priority arrival
                is_quantum_exhausted = False
                if running.mlfq_queue_level == 0 and running.time_slice_used >= self.config.time_quantum:
                    is_quantum_exhausted = True
                elif running.mlfq_queue_level == 1 and running.time_slice_used >= (self.config.time_quantum * 2):
                    is_quantum_exhausted = True

                if is_quantum_exhausted:
                    self.on_full_quantum_used(running)
                    running.time_slice_used = 0
                    # BUG-33 fix: Do NOT raise TIMER interrupt — same double-preempt
                    # issue as RR. Preempt directly instead.

                queue_manager.preempt(tick)

        # Dispatch next process if CPU is idle
        if queue_manager.running is None and queue_manager.ready_queue:
            next_pcb = self.select_next(queue_manager.ready_queue, tick)
            if next_pcb is not None:
                # Ensure newly dispatched processes from ready queue have time slice reset correctly
                queue_manager.dispatch(next_pcb, tick)


# ── Factory Function ──────────────────────────────────────────────────────────

def create_scheduler(config: SchedulerConfig) -> SchedulerAlgorithm:
    """
    Factory function instantiating the requested CPU scheduling algorithm.
    Valid keys: fcfs, sjf, srtf, priority, round_robin, mlfq.
    """
    schedulers = {
        "fcfs": FCFS,
        "sjf": SJF,
        "srtf": SRTF,
        "priority": PriorityScheduler,
        "round_robin": RoundRobin,
        "mlfq": MLFQ,
    }
    cls = schedulers.get(config.algorithm.lower())
    if cls is None:
        raise ValueError(f"Unknown scheduling algorithm: {config.algorithm!r}")
    return cls(config)
