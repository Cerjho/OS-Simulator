# modules/process/queue_manager.py
# Phase: 2 — Process Management
# Owner: Process Agent
"""
QueueManager — manages process lifecycle, queues, and state transitions.
Full implementation spec: OS101_AgentPlan_v2.md Section 7.2
"""
from __future__ import annotations
import collections
from dataclasses import dataclass
from typing import Any

from modules.process.pcb import (
    PCB,
    ProcessState,
    IORequest,
)
from core.interrupt import Interrupt, InterruptController
from core.event_bus import EventBus


# ── GanttEntry & Palette ──────────────────────────────────────────────────────

PALETTE: list[str] = [
    "#4A90E2", "#E25C4A", "#50C878", "#FFB347", "#9B59B6",
    "#1ABC9C", "#E74C3C", "#3498DB", "#F39C12", "#2ECC71",
]


@dataclass
class GanttEntry:
    """One contiguous CPU burst on the Gantt chart."""
    pid:        int
    start_tick: int
    end_tick:   int
    color:      str    # hex color string, e.g. "#4A90E2"
                       # assigned deterministically: color = PALETTE[pid % len(PALETTE)]


class QueueManager:
    """
    Manages all process queues and enforces valid state transitions.

    State owned:
      self.new_queue:             deque[PCB]
      self.ready_queue:           list[PCB]   (managed by scheduler, not sorted here)
      self.running:               PCB | None
      self.blocked:               dict[str, list[PCB]]   key = blocked_reason
      self.terminated:            list[PCB]
      self.gantt_log:             list[GanttEntry]
      self.context_switch_count:  int
    """

    def __init__(self, interrupt_controller: InterruptController, event_bus: EventBus) -> None:
        self.interrupt_controller: InterruptController = interrupt_controller
        self.event_bus: EventBus = event_bus

        self.new_queue: collections.deque[PCB] = collections.deque()
        self.ready_queue: list[PCB] = []
        self.running: PCB | None = None
        self.blocked: dict[str, list[PCB]] = {}
        self.terminated: list[PCB] = []
        self.gantt_log: collections.deque[GanttEntry] = collections.deque(maxlen=200)  # BUG-48 fix
        self.context_switch_count: int = 0

        # Internal tracking for the current Gantt entry being built
        self._current_gantt_start: int | None = None

    # ── Process Creation ──────────────────────────────────────────────────────

    def create_process(
        self,
        name: str,
        burst_time: int,
        priority: int,
        memory_pages: int,
        arrival_time: int,
        sync_requests: list[dict[str, Any]] | None = None,
    ) -> int:
        """Create PCB, place in new_queue, publish PROCESS_CREATED. Return PID."""
        pcb = PCB(
            name=name,
            burst_time=burst_time,
            priority=priority,
            memory_pages=memory_pages,
            arrival_time=arrival_time,
        )
        if sync_requests:
            pcb.sync_requests = sync_requests
        self.new_queue.append(pcb)
        self.event_bus.publish(
            "PROCESS_CREATED",
            {"pid": pcb.pid, "name": pcb.name, "burst_time": pcb.burst_time},
            tick=arrival_time,
            source="queue_manager",
        )
        return pcb.pid

    # ── State Transition Methods ──────────────────────────────────────────────

    def admit(self, pcb: PCB) -> None:
        """Move from new_queue to ready_queue. Transition: NEW → READY."""
        pcb.transition_to(ProcessState.READY, tick=pcb.arrival_time)
        # Remove from new_queue if present
        try:
            self.new_queue.remove(pcb)
        except ValueError:
            pass  # Already removed (e.g., batch admit)
        self.ready_queue.append(pcb)
        self.event_bus.publish(
            "PROCESS_STATE_CHANGED",
            {"pid": pcb.pid, "from": "new", "to": "ready"},
            tick=pcb.arrival_time,
            source="queue_manager",
        )

    def dispatch(self, pcb: PCB, tick: int) -> None:
        """
        Place pcb on CPU. Transition: READY → RUNNING.
        If another process is running, that is a bug (raise RuntimeError).
        Records GanttEntry start.
        Increments context_switch_count.
        """
        if self.running is not None:
            raise RuntimeError(
                f"Cannot dispatch PID {pcb.pid}: PID {self.running.pid} is still running. "
                f"Call preempt() first."
            )
        pcb.transition_to(ProcessState.RUNNING, tick=tick)
        # Remove from ready_queue
        try:
            self.ready_queue.remove(pcb)
        except ValueError:
            pass
        self.running = pcb
        pcb.last_scheduled = tick
        pcb.time_slice_used = 0

        # Start a new Gantt entry
        self._current_gantt_start = tick

        # Count context switch
        self.context_switch_count += 1

        self.event_bus.publish(
            "CONTEXT_SWITCH",
            {"pid": pcb.pid, "tick": tick},
            tick=tick,
            source="queue_manager",
        )

    def preempt(self, tick: int) -> None:
        """
        Remove running process from CPU. RUNNING → READY.
        Close current GanttEntry with end_tick=tick.
        """
        if self.running is None:
            return  # Nothing to preempt

        pcb = self.running
        pcb.transition_to(ProcessState.READY, tick=tick)
        pcb.time_slice_used = 0  # Reset quantum for next scheduling round

        # Close Gantt entry
        self._close_gantt_entry(pcb, tick)

        self.running = None
        self.ready_queue.append(pcb)

        self.event_bus.publish(
            "PROCESS_STATE_CHANGED",
            {"pid": pcb.pid, "from": "running", "to": "ready"},
            tick=tick,
            source="queue_manager",
        )

    def block(self, pcb: PCB, reason: str, tick: int) -> None:
        """
        RUNNING → BLOCKED.
        reason is stored in pcb.blocked_reason and used as dict key.
        Close current GanttEntry.
        """
        pcb.transition_to(ProcessState.BLOCKED, tick=tick)
        pcb.blocked_reason = reason

        # Close Gantt entry
        self._close_gantt_entry(pcb, tick)

        if self.running is pcb:
            self.running = None

        # Add to blocked dict
        if reason not in self.blocked:
            self.blocked[reason] = []
        self.blocked[reason].append(pcb)

        self.event_bus.publish(
            "PROCESS_STATE_CHANGED",
            {"pid": pcb.pid, "from": "running", "to": "blocked", "reason": reason},
            tick=tick,
            source="queue_manager",
        )

    def unblock(self, pcb: PCB, tick: int) -> None:
        """BLOCKED → READY. Remove from blocked dict."""
        pcb.transition_to(ProcessState.READY, tick=tick)

        # Remove from blocked dict
        reason = pcb.blocked_reason
        if reason and reason in self.blocked:
            try:
                self.blocked[reason].remove(pcb)
            except ValueError:
                pass
            # Clean up empty lists
            if not self.blocked[reason]:
                del self.blocked[reason]

        pcb.blocked_reason = None
        self.ready_queue.append(pcb)

        self.event_bus.publish(
            "PROCESS_STATE_CHANGED",
            {"pid": pcb.pid, "from": "blocked", "to": "ready"},
            tick=tick,
            source="queue_manager",
        )

    def terminate(self, pcb: PCB, tick: int) -> None:
        """
        RUNNING → ZOMBIE (if parent alive) or TERMINATED.
        Release all held resources.
        Publish PROCESS_TERMINATED event.
        Append to self.terminated.
        Close GanttEntry.
        """
        # Close Gantt entry
        self._close_gantt_entry(pcb, tick)
        
        if self.running is pcb:
            self.running = None

        is_zombie = False
        if pcb.parent_pid is not None:
            # Find parent
            parent = next((p for p in self.get_all_processes() if p.pid == pcb.parent_pid), None)
            if parent and parent.state not in (ProcessState.TERMINATED, ProcessState.ZOMBIE):
                if parent.state == ProcessState.WAITING:
                    # Parent is waiting for us! Reap immediately and wake parent.
                    pcb.transition_to(ProcessState.TERMINATED, tick)
                    self.unblock(parent, tick)
                else:
                    # Parent is alive but not waiting. We become a ZOMBIE.
                    pcb.transition_to(ProcessState.ZOMBIE, tick)
                    is_zombie = True
            else:
                pcb.transition_to(ProcessState.TERMINATED, tick)
        else:
            pcb.transition_to(ProcessState.TERMINATED, tick)

        self.terminated.append(pcb)

        self.event_bus.publish(
            "PROCESS_TERMINATED",
            {
                "pid": pcb.pid,
                "name": pcb.name,
                "turnaround_time": pcb.turnaround_time,
                "waiting_time": pcb.waiting_time,
                "response_time": pcb.response_time,
                "is_zombie": is_zombie,
            },
            tick=tick,
            source="queue_manager",
        )

    # ── Tick Execution ────────────────────────────────────────────────────────

    def execute_tick(self, tick: int) -> None:
        """
        Decrement running.remaining_burst by 1.
        Increment waiting_time for all READY processes.
        If remaining_burst == 0: call terminate().
        """
        # Increment waiting time for all processes in ready queue
        for pcb in self.ready_queue:
            pcb.waiting_time += 1

        # Execute one burst unit for the running process
        if self.running is not None:
            self.running.remaining_burst -= 1
            self.running.time_slice_used += 1
            self.running.program_counter += 1

            # Check if process has completed
            if self.running.remaining_burst == 0:
                self.terminate(self.running, tick)

    # ── Interrupt Handlers ────────────────────────────────────────────────────

    def handle_timer_interrupt(self, interrupt: Interrupt) -> None:
        """Called by InterruptController on TIMER interrupt. Calls preempt()."""
        if self.running is not None:
            self.preempt(interrupt.raised_at_tick)

    def handle_io_complete(self, interrupt: Interrupt) -> None:
        """Called on IO_COMPLETE. Unblocks the process from interrupt.pid."""
        pid = interrupt.pid
        if pid is None:
            return

        # Find the blocked process with this PID
        for reason, blocked_list in list(self.blocked.items()):
            for pcb in blocked_list:
                if pcb.pid == pid:
                    # Complete the I/O request
                    for io_req in pcb.io_requests:
                        if io_req.completed_at_tick is None:
                            io_req.completed_at_tick = interrupt.raised_at_tick
                            break
                    self.unblock(pcb, interrupt.raised_at_tick)
                    return

    def handle_syscall(self, interrupt: Interrupt) -> None:
        """Handle SYSCALL interrupts: FORK, EXIT, IO_REQUEST."""
        syscall_type = interrupt.data.get("type", "")
        tick = interrupt.raised_at_tick

        if syscall_type == "EXIT":
            if self.running is not None and self.running.pid == interrupt.pid:
                self.terminate(self.running, tick)

        elif syscall_type == "IO_REQUEST":
            if self.running is not None and self.running.pid == interrupt.pid:
                device_id = interrupt.data.get("device_id", "disk0")
                operation = interrupt.data.get("operation", "read")
                size_blocks = interrupt.data.get("size_blocks", 1)
                # BUG-37/38 fix: Use proper import, pass pid field
                io_req = IORequest(
                    device_id=device_id,
                    operation=operation,
                    size_blocks=size_blocks,
                    requested_at_tick=tick,
                    pid=interrupt.pid,
                )
                self.running.io_requests.append(io_req)
                reason = f"io:{device_id}"
                self.block(self.running, reason, tick)

        elif syscall_type == "FORK":
            parent_pid = interrupt.pid
            child_name = interrupt.data.get("child_name", f"child_of_{parent_pid}")
            child_burst = interrupt.data.get("burst_time", interrupt.data.get("child_burst", 5))
            child_priority = interrupt.data.get("priority", 5)
            child_pages = interrupt.data.get("memory_pages", 4)
            child_sync_requests = interrupt.data.get("child_sync_requests", [])
            
            child_pid = self.create_process(
                name=child_name,
                burst_time=child_burst,
                priority=child_priority,
                memory_pages=child_pages,
                arrival_time=tick,
                sync_requests=child_sync_requests
            )
            # Auto-admit the child
            child_pcb = None
            for pcb in self.new_queue:
                if pcb.pid == child_pid:
                    child_pcb = pcb
                    break
            if child_pcb:
                child_pcb.parent_pid = parent_pid
                self.admit(child_pcb)

        elif syscall_type == "WAIT":
            if self.running is not None and self.running.pid == interrupt.pid:
                parent_pcb = self.running
                
                # 1. Check if there is already a ZOMBIE child
                zombie_child = next(
                    (p for p in self.terminated if p.parent_pid == parent_pcb.pid and p.state == ProcessState.ZOMBIE), 
                    None
                )
                if zombie_child:
                    # Reap it immediately, parent continues running
                    zombie_child.transition_to(ProcessState.TERMINATED, tick)
                else:
                    # 2. Check if there are active children
                    active_child = next(
                        (p for p in self.get_all_processes() 
                         if p.parent_pid == parent_pcb.pid and p.state not in (ProcessState.TERMINATED, ProcessState.ZOMBIE)), 
                        None
                    )
                    if active_child:
                        # 3. Put parent to WAITING
                        parent_pcb.transition_to(ProcessState.WAITING, tick)
                        parent_pcb.blocked_reason = "wait_child"
                        
                        self._close_gantt_entry(parent_pcb, tick)
                        self.running = None
                        
                        if "wait_child" not in self.blocked:
                            self.blocked["wait_child"] = []
                        self.blocked["wait_child"].append(parent_pcb)
                        
                        self.event_bus.publish(
                            "PROCESS_STATE_CHANGED",
                            {"pid": parent_pcb.pid, "from": "running", "to": "waiting", "reason": "wait_child"},
                            tick=tick,
                            source="queue_manager",
                        )

    # ── Query Methods ─────────────────────────────────────────────────────────

    def get_all_processes(self) -> list[PCB]:
        """Return all PCBs across all queues, including terminated."""
        result: list[PCB] = []
        result.extend(self.new_queue)
        result.extend(self.ready_queue)
        if self.running is not None:
            result.append(self.running)
        for blocked_list in self.blocked.values():
            result.extend(blocked_list)
        result.extend(self.terminated)
        return result

    def get_statistics(self) -> dict[str, Any]:
        """
        Compute aggregate metrics across all completed processes.
        Returns:
          avg_waiting_time, avg_turnaround_time, avg_response_time,
          throughput (completed / tick), total_context_switches
        """
        completed = self.terminated
        if not completed:
            return {
                "avg_waiting_time": 0.0,
                "avg_turnaround_time": 0.0,
                "avg_response_time": 0.0,
                "throughput": 0.0,
                "total_context_switches": self.context_switch_count,
            }

        n = len(completed)
        avg_waiting = sum(p.waiting_time for p in completed) / n
        avg_turnaround = sum(p.turnaround_time for p in completed) / n
        avg_response = sum(p.response_time for p in completed if p.response_time >= 0) / max(
            1, sum(1 for p in completed if p.response_time >= 0)
        )

        # Throughput: completed processes per tick (use max completion tick)
        max_tick = max((p.completion_tick for p in completed if p.completion_tick is not None), default=1)
        throughput = n / max(1, max_tick)

        return {
            "avg_waiting_time": avg_waiting,
            "avg_turnaround_time": avg_turnaround,
            "avg_response_time": avg_response,
            "throughput": throughput,
            "total_context_switches": self.context_switch_count,
        }

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _close_gantt_entry(self, pcb: PCB, tick: int) -> None:
        """Close the current Gantt entry for the given PCB."""
        if self._current_gantt_start is not None:
            entry = GanttEntry(
                pid=pcb.pid,
                start_tick=self._current_gantt_start,
                end_tick=tick,
                color=PALETTE[pcb.pid % len(PALETTE)],
            )
            self.gantt_log.append(entry)
            # deque(maxlen=200) auto-evicts oldest entries (BUG-48 fix)
            self._current_gantt_start = None
