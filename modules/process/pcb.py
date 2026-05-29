# modules/process/pcb.py
# Phase: 2 — Process Management
# Owner: Process Agent
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProcessState(Enum):
    """
    Valid states and their one-letter codes (used in dashboard display).
    Transitions are defined in the state machine table below.
    """
    NEW        = "new"         # Just created, awaiting admission
    READY      = "ready"       # Ready to run, in ready queue
    RUNNING    = "running"     # On CPU right now
    BLOCKED    = "blocked"     # Waiting for I/O or resource
    WAITING    = "waiting"     # Waiting for child process (join)
    TERMINATED = "terminated"  # Finished execution
    ZOMBIE     = "zombie"      # Terminated, parent not yet notified


# ── Valid State Transitions ───────────────────────────────────────────────────
# Format: (FROM_STATE, TO_STATE) → triggering event
# The QueueManager must ONLY perform transitions listed here.
# Any other transition is a bug and must raise StateTransitionError.

VALID_TRANSITIONS: dict[tuple[ProcessState, ProcessState], str] = {
    (ProcessState.NEW,        ProcessState.READY):      "admit",
    (ProcessState.READY,      ProcessState.RUNNING):    "dispatch",
    (ProcessState.RUNNING,    ProcessState.READY):      "preempt_or_yield",
    (ProcessState.RUNNING,    ProcessState.BLOCKED):    "io_request_or_wait_resource",
    (ProcessState.RUNNING,    ProcessState.WAITING):    "wait_child",
    (ProcessState.RUNNING,    ProcessState.TERMINATED): "exit_or_kill",
    (ProcessState.RUNNING,    ProcessState.ZOMBIE):     "exit_but_parent_alive",
    (ProcessState.BLOCKED,    ProcessState.READY):      "io_complete_or_resource_available",
    (ProcessState.WAITING,    ProcessState.READY):      "child_terminated",
    (ProcessState.TERMINATED, ProcessState.ZOMBIE):     "parent_not_yet_notified",
    (ProcessState.ZOMBIE,     ProcessState.TERMINATED): "parent_notified",  # zombie cleanup
}


class StateTransitionError(Exception):
    """Raised when an invalid PCB state transition is attempted."""
    pass


@dataclass
class IORequest:
    device_id: str
    operation: str       # "read" | "write"
    size_blocks: int
    requested_at_tick: int
    completed_at_tick: int | None = None
    pid: int | None = None          # Process that issued this request
    cylinder: int | None = None     # Target disk cylinder (for disk I/O)


@dataclass
class PageEntry:
    virtual_page:   int
    frame_number:   int | None   # None = not in physical memory (on swap)
    present_bit:    bool = False
    dirty_bit:      bool = False
    reference_bit:  bool = False
    access_time:    int = 0      # tick of last access (for LRU)
    load_time:      int = 0      # tick when loaded into memory (for FIFO)


_next_pid: int = 0

def _allocate_pid() -> int:
    global _next_pid
    _next_pid += 1
    return _next_pid

def reset_pid_counter() -> None:
    """Call before each test to ensure deterministic PIDs."""
    global _next_pid
    _next_pid = 0


@dataclass
class PCB:
    """
    Process Control Block — canonical data record for one process.

    IMMUTABLE after creation: pid, name, parent_pid, arrival_time, burst_time
    MUTABLE during execution: state, remaining_burst, waiting_time, etc.
    """
    # ── Identity (set at creation, never change) ──────────────────────────────
    name:            str
    burst_time:      int           # Total CPU ticks this process needs
    priority:        int = 5       # 0=highest, 99=lowest
    memory_pages:    int = 4       # Number of virtual pages requested
    arrival_time:    int = 0       # Tick when process was created

    # ── Auto-assigned (do not pass manually) ─────────────────────────────────
    pid:             int = field(default_factory=_allocate_pid)
    parent_pid:      int | None = None

    # ── State (mutable) ───────────────────────────────────────────────────────
    state:           ProcessState = ProcessState.NEW

    # ── CPU tracking ──────────────────────────────────────────────────────────
    program_counter:  int = 0
    cpu_registers:    dict[str, int] = field(default_factory=lambda: {"ax": 0, "bx": 0, "cx": 0})
    remaining_burst:  int = field(init=False)
    waiting_time:     int = 0
    turnaround_time:  int = 0
    response_time:    int = -1     # -1 = not yet scheduled even once
    first_scheduled_tick: int | None = None
    completion_tick:  int | None = None

    # ── Scheduling metadata ───────────────────────────────────────────────────
    last_scheduled:   int = 0      # tick of most recent CPU allocation
    time_slice_used:  int = 0      # ticks used in current quantum (for RR)
    mlfq_queue_level: int = 0      # 0 = highest-priority MLFQ queue
    original_priority: int = field(init=False)  # BUG-34 fix: preserved for aging floor

    # ── Memory ────────────────────────────────────────────────────────────────
    memory_base:      int = 0
    memory_limit:     int = 0
    page_table:       list[PageEntry] = field(default_factory=list)
    last_accessed_page: int | None = None

    # ── I/O and Sync ──────────────────────────────────────────────────────────
    io_requests:      list[IORequest] = field(default_factory=list)
    sync_requests:    list[dict[str, Any]] = field(default_factory=list)
    blocked_reason:   str | None = None   # Why process is blocked

    def __post_init__(self) -> None:
        self.remaining_burst = self.burst_time
        self.original_priority = self.priority  # BUG-34 fix: snapshot for aging floor
        # Initialize page table with unmapped entries
        self.page_table = [
            PageEntry(virtual_page=i, frame_number=None, present_bit=False)
            for i in range(self.memory_pages)
        ]

    def transition_to(self, new_state: ProcessState, tick: int) -> None:
        """
        Perform a validated state transition.
        Raises StateTransitionError if the transition is not in VALID_TRANSITIONS.
        """
        key = (self.state, new_state)
        if key not in VALID_TRANSITIONS:
            raise StateTransitionError(
                f"Invalid transition: PCB {self.pid} ({self.name}) "
                f"cannot go from {self.state.value!r} to {new_state.value!r}"
            )
        # Track first scheduling (for response time)
        if new_state == ProcessState.RUNNING and self.first_scheduled_tick is None:
            self.first_scheduled_tick = tick
            self.response_time = tick - self.arrival_time
        # Track completion
        if new_state == ProcessState.TERMINATED:
            self.completion_tick = tick
            self.turnaround_time = tick - self.arrival_time
        self.state = new_state

    def to_dict(self) -> dict[str, Any]:
        """Serializable snapshot for API/dashboard use."""
        return {
            "pid": self.pid,
            "parent_pid": self.parent_pid,
            "name": self.name,
            "state": self.state.value,
            "priority": self.priority,
            "burst_time": self.burst_time,
            "remaining_burst": self.remaining_burst,
            "waiting_time": self.waiting_time,
            "turnaround_time": self.turnaround_time,
            "response_time": self.response_time,
            "arrival_time": self.arrival_time,
            "mlfq_queue_level": self.mlfq_queue_level,
        }
