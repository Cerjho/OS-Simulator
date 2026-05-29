# modules/memory/tlb.py
# Phase: 3 — Memory Management
# Owner: Memory Agent
"""
Translation Lookaside Buffer (TLB) with LRU replacement.
Full implementation spec: OS101_AgentPlan_v2.md Section 8.3
"""
from __future__ import annotations
from collections import OrderedDict


class TLB:
    """
    Translation Lookaside Buffer — a small, fast cache for page-to-frame mappings.

    Rules (from Section 8.3):
      - Uses LRU replacement ONLY.
      - Fully invalidated (all entries flushed) on every context switch.
      - Key: (pid, virtual_page) → frame_number
    """

    def __init__(self, size: int = 16) -> None:
        """Initialize TLB with given capacity (number of entries)."""
        self._size: int = size
        # OrderedDict gives us LRU for free: most-recently-used at the end
        self._cache: OrderedDict[tuple[int, int], int] = OrderedDict()
        self._hit_count: int = 0
        self._miss_count: int = 0

    def lookup(self, pid: int, virtual_page: int) -> int | None:
        """
        Look up a page-to-frame mapping in the TLB.

        Returns the frame number on hit (and moves entry to most-recently-used),
        or None on miss. Tracks hit/miss counts for statistics.
        """
        key = (pid, virtual_page)
        if key in self._cache:
            self._hit_count += 1
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return self._cache[key]
        else:
            self._miss_count += 1
            return None

    def insert(self, pid: int, virtual_page: int, frame: int) -> None:
        """
        Insert a page-to-frame mapping into the TLB.

        If the TLB is full, evicts the least-recently-used entry first.
        If the entry already exists, updates it and marks as most recently used.
        """
        key = (pid, virtual_page)
        if key in self._cache:
            # Update existing entry and move to end
            self._cache.move_to_end(key)
            self._cache[key] = frame
        else:
            # Evict LRU entry if at capacity
            if len(self._cache) >= self._size:
                self._cache.popitem(last=False)  # Remove oldest (LRU)
            self._cache[key] = frame

    def invalidate(self, pid: int) -> None:
        """
        Remove all TLB entries for the given PID.
        Called on context switch to flush stale mappings.
        """
        keys_to_remove = [k for k in self._cache if k[0] == pid]
        for key in keys_to_remove:
            del self._cache[key]

    def invalidate_all(self) -> None:
        """Flush the entire TLB. Called on every context switch."""
        self._cache.clear()

    def invalidate_page(self, pid: int, virtual_page: int) -> None:
        """Remove a specific page mapping from the TLB."""
        key = (pid, virtual_page)
        if key in self._cache:
            del self._cache[key]

    @property
    def hit_count(self) -> int:
        """Total number of TLB hits since creation."""
        return self._hit_count

    @property
    def miss_count(self) -> int:
        """Total number of TLB misses since creation."""
        return self._miss_count

    @property
    def hit_rate(self) -> float:
        """TLB hit rate as a fraction [0.0, 1.0]. Returns 0.0 if no accesses."""
        total = self._hit_count + self._miss_count
        if total == 0:
            return 0.0
        return self._hit_count / total

    @property
    def size(self) -> int:
        """Maximum number of entries the TLB can hold."""
        return self._size

    @property
    def current_entries(self) -> int:
        """Number of entries currently in the TLB."""
        return len(self._cache)

    def reset_stats(self) -> None:
        """Reset hit/miss counters (but keep cached entries)."""
        self._hit_count = 0
        self._miss_count = 0
