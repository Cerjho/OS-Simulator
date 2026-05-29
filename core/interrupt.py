# core/interrupt.py
from __future__ import annotations
import heapq
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any


class InterruptType(Enum):
    """
    Interrupt types in PRIORITY ORDER (lower value = higher priority).
    The interrupt controller dispatches highest-priority pending interrupt first.
    """
    HARDWARE_ERR = 0   # Simulated hardware fault — highest priority
    PAGE_FAULT   = 1   # Page not in physical memory
    TIMER        = 2   # Preempt current process (fires every time_quantum ticks)
    IO_COMPLETE  = 3   # I/O operation finished; unblock a process
    SYSCALL      = 4   # Process requested an OS service — lowest priority


@dataclass(order=True)
class Interrupt:
    priority: int          # Derived from InterruptType.value
    interrupt_type: InterruptType = field(compare=False)
    pid: int | None = field(compare=False, default=None)
    data: dict[str, Any] = field(compare=False, default_factory=dict)
    raised_at_tick: int = field(compare=False, default=0)


class InterruptController:
    """
    Priority-queue-based interrupt dispatcher.

    Usage:
      ic = InterruptController()
      ic.register_handler(InterruptType.TIMER, my_handler)
      ic.raise_interrupt(InterruptType.TIMER, pid=1)
      await ic.handle_next(current_tick)
    """

    def __init__(self) -> None:
        self._queue: list[Interrupt] = []
        self._handlers: dict[InterruptType, Callable[[Interrupt], None]] = {}

    def register_handler(
        self,
        interrupt_type: InterruptType,
        handler: Callable[[Interrupt], None],
    ) -> None:
        """Bind a handler function for an interrupt type. One handler per type."""
        self._handlers[interrupt_type] = handler

    def raise_interrupt(
        self,
        interrupt_type: InterruptType,
        pid: int | None = None,
        data: dict[str, Any] | None = None,
        current_tick: int = 0,
    ) -> None:
        """Enqueue an interrupt. Safe to call from any subsystem."""
        interrupt = Interrupt(
            priority=interrupt_type.value,
            interrupt_type=interrupt_type,
            pid=pid,
            data=data or {},
            raised_at_tick=current_tick,
        )
        heapq.heappush(self._queue, interrupt)

    def handle_next(self) -> bool:
        """
        Dispatch the highest-priority pending interrupt.
        Returns True if an interrupt was handled, False if queue was empty.
        """
        if not self._queue:
            return False
        interrupt = heapq.heappop(self._queue)
        handler = self._handlers.get(interrupt.interrupt_type)
        if handler is None:
            # No handler registered — log and discard
            print(f"[WARN] No handler for interrupt {interrupt.interrupt_type.name}, discarding")
            return True
        handler(interrupt)
        return True

    def handle_all(self) -> int:
        """Handle all currently pending interrupts. Returns count handled."""
        count = 0
        while self.handle_next():
            count += 1
        return count

    def pending_count(self) -> int:
        return len(self._queue)

    def clear(self) -> None:
        """Discard all pending interrupts. Use only for reset."""
        self._queue.clear()
