# modules/memory/paging.py
# Phase: 3 — Memory Management
# Owner: Memory Agent
"""
VirtualMemoryManager with FIFO, LRU, Clock, and Optimal page replacement.
Full implementation spec: OS101_AgentPlan_v2.md Sections 8.2, 8.4
"""
from __future__ import annotations
import sys
from typing import Any

from core.config import MemoryConfig
from core.interrupt import InterruptController
from modules.memory.tlb import TLB


class VirtualMemoryManager:
    """
    Manages virtual-to-physical address translation with demand paging.

    Supports four page replacement algorithms:
      - FIFO: evict page with smallest load_time
      - LRU:  evict page with smallest access_time
      - Clock (Second-Chance): circular scan with reference_bit
      - Optimal (Oracle): evict page used furthest in future
    """

    def __init__(self, config: MemoryConfig, interrupt_controller: InterruptController) -> None:
        self._config: MemoryConfig = config
        self._interrupt_controller: InterruptController = interrupt_controller

        # Frame table: frame_number → (pid, virtual_page) or None if free
        self._total_frames: int = config.total_frames
        self._frame_table: dict[int, tuple[int, int] | None] = {
            i: None for i in range(self._total_frames)
        }

        # Per-process page tables: pid → {virtual_page → PageTableEntry}
        self._page_tables: dict[int, dict[int, _PageTableEntry]] = {}

        # Swap space: (pid, virtual_page) → data bytes
        self._swap_space: dict[tuple[int, int], bytes] = {}

        # TLB (size=0 disables it)
        self._tlb: TLB = TLB(size=config.tlb_size) if config.tlb_size > 0 else TLB(size=0)

        # Statistics
        self._page_fault_count: int = 0
        self._total_accesses: int = 0

        # Clock algorithm pointer
        self._clock_hand: int = 0

        # For optimal algorithm: future access sequence (set externally)
        self._future_accesses: list[tuple[int, int]] = []  # [(pid, page), ...]
        self._future_access_cursor: int = 0  # BUG-36 fix: track position in oracle list

        # Algorithm selection
        self._algorithm: str = config.algorithm

    # ── Address Translation ───────────────────────────────────────────────────

    def translate(self, pid: int, virtual_page: int, tick: int) -> int | None:
        """
        Translate virtual_page for pid to physical frame number.

        Steps:
          1. Check TLB → return frame if hit
          2. Check page table → if present: load to TLB, return frame
          3. If not present: return None (caller should invoke page fault handler)

        Updates reference_bit and access_time on every successful access.
        """
        self._total_accesses += 1
        # BUG-36 fix: advance cursor for optimal algorithm to skip past accesses
        if self._algorithm == "optimal" and self._future_access_cursor < len(self._future_accesses):
            self._future_access_cursor += 1

        # Step 1: TLB lookup
        if self._tlb.size > 0:
            frame = self._tlb.lookup(pid, virtual_page)
            if frame is not None:
                # Update access metadata in page table
                self._update_access(pid, virtual_page, tick)
                return frame

        # Step 2: Page table lookup
        entry = self._get_page_entry(pid, virtual_page)
        if entry is not None and entry.present:
            # Page is in memory — update TLB and access metadata
            if self._tlb.size > 0:
                self._tlb.insert(pid, virtual_page, entry.frame)
            self._update_access(pid, virtual_page, tick)
            return entry.frame

        # Step 3: Page fault — page not in physical memory
        return None

    def handle_page_fault(self, interrupt: Any) -> None:
        """
        Called by InterruptController on PAGE_FAULT.
        interrupt.data keys: pid (int), page_num (int)
        """
        pid = interrupt.data.get("pid", 0)
        page_num = interrupt.data.get("page_num", 0)
        tick = interrupt.raised_at_tick
        self.handle_page_fault_direct(pid, page_num, tick)

    def handle_page_fault_direct(self, pid: int, page_num: int, tick: int) -> None:
        """
        Direct page fault handler for testing without interrupts.

        Steps:
          1. If free frame available: load page from swap into frame
          2. If no free frame: run eviction (config.algorithm), then load
          3. Update page table entry: present=True, frame=allocated_frame
          4. Update TLB
          5. Increment page_fault_count
        """
        self._page_fault_count += 1

        # Find a free frame
        frame = self._find_free_frame()

        if frame is None:
            # No free frame — evict a page
            evicted_pid, evicted_page = self.evict_page(tick)
            evicted_entry = self._get_page_entry(evicted_pid, evicted_page)
            if evicted_entry is not None:
                frame = evicted_entry.frame
                # If dirty, write to swap
                if evicted_entry.dirty:
                    self._swap_space[(evicted_pid, evicted_page)] = b"swapped"
                # Mark evicted page as not present
                evicted_entry.present = False
                evicted_entry.frame = -1
                # Invalidate TLB entry for evicted page
                if self._tlb.size > 0:
                    self._tlb.invalidate_page(evicted_pid, evicted_page)
                # Update frame table
                self._frame_table[frame] = None

        if frame is None:  # pragma: no cover
            return  # Defensive: eviction always yields a frame

        # Load page into frame
        self._ensure_page_table(pid)
        entry = self._get_or_create_entry(pid, page_num)
        entry.frame = frame
        entry.present = True
        entry.reference = True
        entry.access_time = tick
        entry.load_time = tick
        entry.dirty = False

        # Update frame table
        self._frame_table[frame] = (pid, page_num)

        # Update TLB
        if self._tlb.size > 0:
            self._tlb.insert(pid, page_num, frame)

    def evict_page(self, tick: int) -> tuple[int, int]:
        """
        Select and evict a page using configured replacement algorithm.
        Returns (pid, page_num) of evicted page.
        """
        if self._algorithm == "fifo":
            return self._evict_fifo()
        elif self._algorithm == "lru":
            return self._evict_lru()
        elif self._algorithm == "clock":
            return self._evict_clock()
        elif self._algorithm == "optimal":
            return self._evict_optimal(tick)
        else:
            return self._evict_lru()  # Default fallback

    def free_process(self, pid: int) -> None:
        """
        Release all physical frames, page table entries, and TLB entries for a process.
        Called by the kernel when a process terminates.
        """
        # Free all frames belonging to this PID
        for frame_num, occupant in list(self._frame_table.items()):
            if occupant is not None and occupant[0] == pid:
                self._frame_table[frame_num] = None
        # Remove page table for this PID
        if pid in self._page_tables:
            del self._page_tables[pid]
        # Remove swap entries for this PID
        swap_keys_to_remove = [k for k in self._swap_space if k[0] == pid]
        for key in swap_keys_to_remove:
            del self._swap_space[key]
        # Invalidate TLB entries
        if self._tlb.size > 0:
            self._tlb.invalidate(pid)

    def tick(self, tick: int) -> None:
        """Called every tick by the kernel. Currently no periodic work needed."""
        pass

    # ── Statistics ─────────────────────────────────────────────────────────────

    def get_page_fault_count(self) -> int:
        """Total page faults since start."""
        return self._page_fault_count

    def get_page_fault_rate(self) -> float:
        """Page faults / total accesses."""
        if self._total_accesses == 0:
            return 0.0
        return self._page_fault_count / self._total_accesses

    def get_tlb_hit_rate(self) -> float:
        """TLB hit rate."""
        return self._tlb.hit_rate

    def get_state_snapshot(self) -> dict[str, Any]:
        """Return serializable state for API/dashboard."""
        used_frames = sum(1 for v in self._frame_table.values() if v is not None)
        return {
            "total_frames": self._total_frames,
            "used_frames": used_frames,
            "free_frames": self._total_frames - used_frames,
            "utilization": used_frames / self._total_frames if self._total_frames > 0 else 0.0,
            "page_fault_count": self._page_fault_count,
            "page_fault_rate": self.get_page_fault_rate(),
            "tlb_hit_rate": self.get_tlb_hit_rate(),
            "total_accesses": self._total_accesses,
            "swap_pages": len(self._swap_space),
            "algorithm": self._algorithm,
        }

    def set_future_accesses(self, accesses: list[tuple[int, int]]) -> None:
        """Set the future access sequence for the Optimal algorithm."""
        self._future_accesses = list(accesses)
        self._future_access_cursor = 0  # BUG-36 fix: reset cursor on new sequence

    def get_allocated_blocks(self) -> list[dict[str, int]]:
        """
        Return contiguous memory block allocations for dashboard visualization.
        BUG-40 fix: public API so kernel doesn't access _frame_table directly.
        Returns list of {base, size, pid} dicts for occupied frame runs.
        """
        occupied: list[tuple[int, int]] = []  # (frame_num, pid)
        for frame_num, occupant in self._frame_table.items():
            if occupant is not None:
                pid, _page = occupant
                occupied.append((frame_num, pid))
        occupied.sort(key=lambda x: x[0])

        blocks: list[dict[str, int]] = []
        if occupied:
            run_base, run_pid = occupied[0]
            run_size = 1
            for i in range(1, len(occupied)):
                frame_num, pid = occupied[i]
                if pid == run_pid and frame_num == run_base + run_size:
                    run_size += 1
                else:
                    blocks.append({"base": run_base, "size": run_size, "pid": run_pid})
                    run_base, run_pid, run_size = frame_num, pid, 1
            blocks.append({"base": run_base, "size": run_size, "pid": run_pid})
        return blocks

    # ── Eviction Algorithms ───────────────────────────────────────────────────

    def _evict_fifo(self) -> tuple[int, int]:
        """
        FIFO: Evict the page that has been in memory the LONGEST (smallest load_time).
        Do NOT use access_time for FIFO. Only load_time matters.
        """
        victim_pid: int = -1
        victim_page: int = -1
        oldest_load_time: int = sys.maxsize

        for frame_num, occupant in self._frame_table.items():
            if occupant is None:  # pragma: no cover
                continue  # Defensive: eviction only runs when all frames occupied
            pid, page = occupant
            entry = self._get_page_entry(pid, page)
            if entry is not None and entry.present:
                if entry.load_time < oldest_load_time:
                    oldest_load_time = entry.load_time
                    victim_pid = pid
                    victim_page = page

        return (victim_pid, victim_page)

    def _evict_lru(self) -> tuple[int, int]:
        """
        LRU: Evict the page that was accessed LEAST RECENTLY (smallest access_time).
        """
        victim_pid: int = -1
        victim_page: int = -1
        oldest_access_time: int = sys.maxsize

        for frame_num, occupant in self._frame_table.items():
            if occupant is None:  # pragma: no cover
                continue  # Defensive: eviction only runs when all frames occupied
            pid, page = occupant
            entry = self._get_page_entry(pid, page)
            if entry is not None and entry.present:
                if entry.access_time < oldest_access_time:
                    oldest_access_time = entry.access_time
                    victim_pid = pid
                    victim_page = page

        return (victim_pid, victim_page)

    def _evict_clock(self) -> tuple[int, int]:
        """
        Clock (Second-Chance): circular scan with reference_bit.
        Scan clockwise; if reference_bit=True, clear it and advance.
        Evict the first page with reference_bit=False.
        """
        num_frames = self._total_frames
        # We may need to cycle through all frames twice in worst case
        for _ in range(2 * num_frames):
            frame = self._clock_hand % num_frames
            self._clock_hand = (self._clock_hand + 1) % num_frames

            occupant = self._frame_table.get(frame)
            if occupant is None:  # pragma: no cover
                continue  # Defensive: clock scans occupied frames only

            pid, page = occupant
            entry = self._get_page_entry(pid, page)
            if entry is None or not entry.present:  # pragma: no cover
                continue  # Defensive: occupied frames always have valid entries

            if entry.reference:
                # Give second chance — clear reference bit
                entry.reference = False
            else:
                # Evict this page
                return (pid, page)

        # Fallback: evict the current clock hand position  # pragma: no cover
        frame = self._clock_hand % num_frames  # pragma: no cover
        occupant = self._frame_table.get(frame)  # pragma: no cover
        if occupant is not None:  # pragma: no cover
            return occupant  # pragma: no cover
        return (-1, -1)  # pragma: no cover

    def _evict_optimal(self, tick: int) -> tuple[int, int]:
        """
        Optimal (Oracle): Evict the page that will not be used for the LONGEST future time.
        Requires future access sequence to be set via set_future_accesses().
        """
        # Build future access index from current position
        present_pages: list[tuple[int, int]] = []
        for frame_num, occupant in self._frame_table.items():
            if occupant is not None:
                present_pages.append(occupant)

        if not present_pages:
            return (-1, -1)

        # Find next use of each present page in the future sequence
        best_victim: tuple[int, int] = present_pages[0]
        farthest_use: int = -1

        # BUG-36 fix: scan from cursor position, not index 0
        future_slice = self._future_accesses[self._future_access_cursor:]

        for pid, page in present_pages:
            # Find next occurrence in future accesses
            # BUG-35 fix: Use sys.maxsize instead of float('inf') for type safety
            next_use: int = sys.maxsize
            for i, (fpid, fpage) in enumerate(future_slice):
                if fpid == pid and fpage == page:
                    next_use = i
                    break

            if next_use == sys.maxsize:
                # Page never used again — best victim
                return (pid, page)

            if next_use > farthest_use:
                farthest_use = next_use
                best_victim = (pid, page)

        return best_victim

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _find_free_frame(self) -> int | None:
        """Find a free frame. Returns frame number or None."""
        for frame_num, occupant in self._frame_table.items():
            if occupant is None:
                return frame_num
        return None

    def _ensure_page_table(self, pid: int) -> None:
        """Create page table for pid if it doesn't exist."""
        if pid not in self._page_tables:
            self._page_tables[pid] = {}

    def _get_page_entry(self, pid: int, virtual_page: int) -> _PageTableEntry | None:
        """Get page table entry for (pid, virtual_page), or None."""
        if pid not in self._page_tables:
            return None
        return self._page_tables[pid].get(virtual_page)

    def _get_or_create_entry(self, pid: int, virtual_page: int) -> _PageTableEntry:
        """Get or create a page table entry."""
        self._ensure_page_table(pid)
        if virtual_page not in self._page_tables[pid]:
            self._page_tables[pid][virtual_page] = _PageTableEntry()
        return self._page_tables[pid][virtual_page]

    def _update_access(self, pid: int, virtual_page: int, tick: int) -> None:
        """Update access metadata on a page table entry."""
        entry = self._get_page_entry(pid, virtual_page)
        if entry is not None:
            entry.access_time = tick
            entry.reference = True


class _PageTableEntry:
    """Internal page table entry used by VirtualMemoryManager."""

    __slots__ = ('frame', 'present', 'dirty', 'reference', 'access_time', 'load_time')

    def __init__(self) -> None:
        self.frame: int = -1
        self.present: bool = False
        self.dirty: bool = False
        self.reference: bool = False
        self.access_time: int = 0
        self.load_time: int = 0
