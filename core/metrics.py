# core/metrics.py
# Phase: 9 — Metrics Collection
# Owner: Dashboard Agent
"""
MetricsCollector — lightweight per-tick telemetry aggregator.
Records CPU utilization, page fault rates, and memory utilization
for historical time-series dashboards.
"""
from __future__ import annotations
import collections
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from modules.process.queue_manager import QueueManager
    from modules.memory.paging import VirtualMemoryManager


class MetricsCollector:
    """
    Collects per-tick metrics from kernel subsystems.

    Owned by Kernel; receives subsystem references after _init_subsystems().
    """

    def __init__(self) -> None:
        self._process_manager: QueueManager | None = None
        self._memory_manager: VirtualMemoryManager | None = None

        # Running counters
        self._busy_ticks: int = 0
        self._total_ticks: int = 0

        # Per-tick history (ring buffer, capped at 1000 entries)
        # BUG-41 fix: Use deque with maxlen for O(1) append and auto-eviction
        self._max_history: int = 1000
        self._history: collections.deque[dict[str, Any]] = collections.deque(maxlen=self._max_history)

    def bind(
        self,
        process_manager: QueueManager | None = None,
        memory_manager: VirtualMemoryManager | None = None,
    ) -> None:
        """Bind subsystem references after kernel initialisation."""
        self._process_manager = process_manager
        self._memory_manager = memory_manager

    # ── Public Metrics ─────────────────────────────────────────────────────────

    def cpu_utilization(self) -> float:
        """Overall CPU utilization since simulation start (0.0 – 1.0)."""
        if self._total_ticks == 0:
            return 0.0
        return self._busy_ticks / self._total_ticks

    def current_page_fault_rate(self) -> float:
        if self._memory_manager is None:
            return 0.0
        return self._memory_manager.get_page_fault_rate()

    def current_memory_utilization(self) -> float:
        if self._memory_manager is None:
            return 0.0
        snap = self._memory_manager.get_state_snapshot()
        return snap.get("utilization", 0.0)

    def get_history(self, last_n: int = 100) -> list[dict[str, Any]]:
        """Return the last *last_n* history records."""
        return self._history[-last_n:]

    # ── Tick ───────────────────────────────────────────────────────────────────

    def tick(self, current_tick: int) -> None:
        """Sample subsystem metrics and append to history ring buffer."""
        self._total_ticks += 1

        # CPU busy if a process is currently on the CPU
        if self._process_manager and self._process_manager.running is not None:
            self._busy_ticks += 1

        record = {
            "tick": current_tick,
            "cpu_utilization": self.cpu_utilization(),
            "page_fault_rate": self.current_page_fault_rate(),
            "memory_utilization": self.current_memory_utilization(),
        }
        self._history.append(record)  # deque auto-evicts oldest when maxlen reached
