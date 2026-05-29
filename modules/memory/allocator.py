# modules/memory/allocator.py
# Phase: 3 — Memory Management
# Owner: Memory Agent
"""
Physical frame allocator with first_fit, best_fit, worst_fit algorithms.
Enforces INV-3: free_frames + allocated_frames == total_frames at all times.
Full implementation spec: OS101_AgentPlan_v2.md Section 8.1
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any


@dataclass
class MemoryBlock:
    """A contiguous block of physical memory frames."""
    base: int       # Starting frame number
    size: int       # Number of frames in this block
    pid: int | None = None  # None = free block


class MemoryAllocator:
    """
    Physical frame allocator using contiguous allocation.

    INVARIANT (INV-3): free_frames + allocated_frames == total_frames at ALL times.
    An assert checks this at the end of every allocate() and deallocate() call.
    """

    def __init__(self, total_frames: int) -> None:
        """
        Initialize with total_frames physical frames (numbered 0 to total_frames-1).
        All frames start FREE.
        """
        self._total_frames: int = total_frames
        # Start with one big free block
        self._blocks: list[MemoryBlock] = [MemoryBlock(base=0, size=total_frames, pid=None)]
        self._algorithm: str = "first_fit"  # Default algorithm

    def set_algorithm(self, algorithm: str) -> None:
        """Set allocation algorithm: 'first_fit', 'best_fit', or 'worst_fit'."""
        valid = {"first_fit", "best_fit", "worst_fit"}
        if algorithm not in valid:
            raise ValueError(f"Invalid allocation algorithm: {algorithm!r}. Must be one of {valid}")
        self._algorithm = algorithm

    def allocate(self, pid: int, num_frames: int) -> list[int] | None:
        """
        Allocate num_frames contiguous frames to pid.
        Returns list of allocated frame numbers, or None if insufficient.
        Uses the configured algorithm (first_fit | best_fit | worst_fit).
        """
        if num_frames <= 0:
            return None

        # Find a suitable free block using the configured algorithm
        block_idx = self._find_free_block(num_frames)
        if block_idx is None:
            return None

        free_block = self._blocks[block_idx]
        allocated_base = free_block.base
        allocated_frames = list(range(allocated_base, allocated_base + num_frames))

        # Split the block: create allocated block and shrink/remove free block
        new_allocated = MemoryBlock(base=allocated_base, size=num_frames, pid=pid)

        if free_block.size == num_frames:
            # Exact fit — replace the free block
            self._blocks[block_idx] = new_allocated
        else:
            # Split: insert allocated block, shrink free block
            remaining = MemoryBlock(
                base=allocated_base + num_frames,
                size=free_block.size - num_frames,
                pid=None,
            )
            self._blocks[block_idx] = new_allocated
            self._blocks.insert(block_idx + 1, remaining)

        self._assert_invariant()
        return allocated_frames

    def deallocate(self, pid: int) -> list[int]:
        """
        Free all frames held by pid.
        Returns list of freed frame numbers.
        Coalesces adjacent free blocks automatically.
        """
        freed_frames: list[int] = []

        # Mark all blocks owned by pid as free
        for block in self._blocks:
            if block.pid == pid:
                freed_frames.extend(range(block.base, block.base + block.size))
                block.pid = None

        # Coalesce adjacent free blocks
        self._coalesce()

        self._assert_invariant()
        return freed_frames

    def get_free_frame_count(self) -> int:
        """Returns number of currently free frames."""
        return sum(b.size for b in self._blocks if b.pid is None)

    def get_allocated_frame_count(self) -> int:
        """Returns number of currently allocated frames."""
        return sum(b.size for b in self._blocks if b.pid is not None)

    def get_fragmentation(self) -> dict[str, float]:
        """
        Returns:
          internal_fragmentation: wasted space inside allocated regions (%)
          external_fragmentation: free space not usable due to fragmentation (%)
        """
        free_blocks = [b for b in self._blocks if b.pid is None]
        total_free = sum(b.size for b in free_blocks)

        if total_free == 0:
            return {"internal_fragmentation": 0.0, "external_fragmentation": 0.0}

        # External fragmentation: 1 - (largest_free_block / total_free)
        largest_free = max((b.size for b in free_blocks), default=0)
        external = 1.0 - (largest_free / total_free) if total_free > 0 else 0.0

        # Internal fragmentation: not modeled in frame-level allocation (always 0)
        # In real OS, this occurs within pages, but we allocate whole frames
        internal = 0.0

        return {
            "internal_fragmentation": internal * 100.0,
            "external_fragmentation": external * 100.0,
        }

    def visualize(self) -> list[dict[str, Any]]:
        """
        Returns ordered list of memory blocks for dashboard rendering.
        Each block: {"base": int, "size": int, "pid": int | None}
        pid=None means FREE.
        """
        return [
            {"base": b.base, "size": b.size, "pid": b.pid}
            for b in self._blocks
        ]

    def compact(self) -> None:
        """
        Defragment: move all allocated blocks to one end, merge free space.
        This is a stop-the-world operation (takes context_switch_cost ticks).
        """
        allocated_blocks: list[MemoryBlock] = []
        total_free = 0

        for block in self._blocks:
            if block.pid is not None:
                allocated_blocks.append(block)
            else:
                total_free += block.size

        # Rebuild: all allocated blocks packed at the start
        new_blocks: list[MemoryBlock] = []
        current_base = 0
        for block in allocated_blocks:
            new_blocks.append(MemoryBlock(base=current_base, size=block.size, pid=block.pid))
            current_base += block.size

        # One big free block at the end
        if total_free > 0:
            new_blocks.append(MemoryBlock(base=current_base, size=total_free, pid=None))

        self._blocks = new_blocks
        self._assert_invariant()

    def get_state_snapshot(self) -> dict[str, Any]:
        """Return serializable state for API/dashboard."""
        return {
            "total_frames": self._total_frames,
            "free_frames": self.get_free_frame_count(),
            "allocated_frames": self.get_allocated_frame_count(),
            "blocks": self.visualize(),
            "fragmentation": self.get_fragmentation(),
        }

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _find_free_block(self, num_frames: int) -> int | None:
        """Find a suitable free block index using the configured algorithm."""
        if self._algorithm == "first_fit":
            return self._first_fit(num_frames)
        elif self._algorithm == "best_fit":
            return self._best_fit(num_frames)
        elif self._algorithm == "worst_fit":
            return self._worst_fit(num_frames)
        return self._first_fit(num_frames)  # pragma: no cover — defensive fallback

    def _first_fit(self, num_frames: int) -> int | None:
        """Return index of first free block large enough."""
        for i, block in enumerate(self._blocks):
            if block.pid is None and block.size >= num_frames:
                return i
        return None

    def _best_fit(self, num_frames: int) -> int | None:
        """Return index of smallest free block large enough."""
        best_idx: int | None = None
        best_size: int = self._total_frames + 1

        for i, block in enumerate(self._blocks):
            if block.pid is None and block.size >= num_frames:
                if block.size < best_size:
                    best_size = block.size
                    best_idx = i
        return best_idx

    def _worst_fit(self, num_frames: int) -> int | None:
        """Return index of largest free block large enough."""
        worst_idx: int | None = None
        worst_size: int = -1

        for i, block in enumerate(self._blocks):
            if block.pid is None and block.size >= num_frames:
                if block.size > worst_size:
                    worst_size = block.size
                    worst_idx = i
        return worst_idx

    def _coalesce(self) -> None:
        """Merge adjacent free blocks."""
        if len(self._blocks) <= 1:
            return

        merged: list[MemoryBlock] = [self._blocks[0]]
        for block in self._blocks[1:]:
            prev = merged[-1]
            if prev.pid is None and block.pid is None:
                # Merge adjacent free blocks
                merged[-1] = MemoryBlock(base=prev.base, size=prev.size + block.size, pid=None)
            else:
                merged.append(block)
        self._blocks = merged

    def _assert_invariant(self) -> None:
        """INV-3: free_frames + allocated_frames == total_frames"""
        free = self.get_free_frame_count()
        allocated = self.get_allocated_frame_count()
        total = free + allocated
        assert total == self._total_frames, (
            f"INV-3 VIOLATED: free({free}) + allocated({allocated}) = {total} "
            f"!= total_frames({self._total_frames})"
        )
