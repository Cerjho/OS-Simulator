# modules/io/disk.py
# Phase: 5 — I/O & Device Management
# Owner: IO Agent
"""
Disk scheduling algorithms implementation.
Full implementation spec: OS101_AgentPlan_v2.md Section 10
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from core.config import DiskConfig


@dataclass
class DiskRequest:
    """Represents a pending or serviced disk I/O request."""
    cylinder:      int
    pid:           int
    request_id:    str
    arrival_tick:  int = 0
    seek_distance: int | None = None
    service_tick:  int | None = None


class DiskScheduler:
    """
    Disk scheduling engine supporting 6 algorithms:
    FCFS, SSTF, SCAN, C-SCAN, LOOK, C-LOOK.

    Enforces exact textbook seek sequences and distances.
    """

    def __init__(self, config: DiskConfig) -> None:
        self._config: DiskConfig = config
        self.current_head: int = config.initial_head
        self.direction: int = +1  # +1 = ascending, -1 = descending
        self.pending: list[DiskRequest] = []
        self.algorithm: str = config.scheduling.lower()
        self.total_seek_distance: int = 0
        self.seek_trace: list[tuple[int, int, int]] = []  # (from, to, distance)

        self._cylinders: int = config.cylinders
        self._current_tick: int = 0

    @property
    def total_cylinders(self) -> int:
        """Public accessor for total cylinder count (FE-BUG-06 fix)."""
        return self._cylinders

    def add_request(self, cylinder: int, pid: int, request_id: str) -> None:
        """Enqueue a disk request. cylinder must be in [0, config.cylinders-1]."""
        if not (0 <= cylinder < self._cylinders):
            raise ValueError(f"Cylinder {cylinder} out of bounds [0, {self._cylinders - 1}]")
        req = DiskRequest(
            cylinder=cylinder,
            pid=pid,
            request_id=request_id,
            arrival_tick=self._current_tick,
        )
        self.pending.append(req)

    def select_next(self) -> DiskRequest | None:
        """
        Select next request using configured algorithm.
        Returns None if queue is empty.
        DOES NOT move the disk head — just selects.
        """
        if not self.pending:
            return None

        if self.algorithm == "fcfs":
            return self.pending[0]

        elif self.algorithm == "sstf":
            # Shortest Seek Time First
            best_req = self.pending[0]
            min_dist = abs(best_req.cylinder - self.current_head)
            for req in self.pending[1:]:
                dist = abs(req.cylinder - self.current_head)
                if dist < min_dist:
                    min_dist = dist
                    best_req = req
            return best_req

        elif self.algorithm == "scan":
            # Sweeps in current direction, reverses at boundary
            if self.direction == 1:
                # Ahead or at current head
                ahead = [r for r in self.pending if r.cylinder >= self.current_head]
                if ahead:
                    return min(ahead, key=lambda r: r.cylinder)
                # Need to reverse direction to service remaining
                behind = [r for r in self.pending if r.cylinder < self.current_head]
                if behind:
                    return max(behind, key=lambda r: r.cylinder)
            else:
                # Behind or at current head
                behind = [r for r in self.pending if r.cylinder <= self.current_head]
                if behind:
                    return max(behind, key=lambda r: r.cylinder)
                # Need to reverse direction to service remaining
                ahead = [r for r in self.pending if r.cylinder > self.current_head]
                if ahead:
                    return min(ahead, key=lambda r: r.cylinder)
            return self.pending[0]  # pragma: no cover — defensive fallback

        elif self.algorithm == "c-scan":
            # Always sweeps in +1 direction, jumps to 0 at end
            ahead = [r for r in self.pending if r.cylinder >= self.current_head]
            if ahead:
                return min(ahead, key=lambda r: r.cylinder)
            # Wrap around to lowest cylinder
            return min(self.pending, key=lambda r: r.cylinder)

        elif self.algorithm == "look":
            # Sweeps in current direction, reverses at last request
            if self.direction == 1:
                ahead = [r for r in self.pending if r.cylinder >= self.current_head]
                if ahead:
                    return min(ahead, key=lambda r: r.cylinder)
                behind = [r for r in self.pending if r.cylinder < self.current_head]
                if behind:
                    return max(behind, key=lambda r: r.cylinder)
            else:
                behind = [r for r in self.pending if r.cylinder <= self.current_head]
                if behind:
                    return max(behind, key=lambda r: r.cylinder)
                ahead = [r for r in self.pending if r.cylinder > self.current_head]
                if ahead:
                    return min(ahead, key=lambda r: r.cylinder)
            return self.pending[0]  # pragma: no cover — defensive fallback

        elif self.algorithm == "c-look":
            # Always sweeps in +1 direction, jumps to lowest request
            ahead = [r for r in self.pending if r.cylinder >= self.current_head]
            if ahead:
                return min(ahead, key=lambda r: r.cylinder)
            return min(self.pending, key=lambda r: r.cylinder)

        return self.pending[0]  # pragma: no cover — defensive fallback

    def service_next(self) -> DiskRequest | None:
        """
        Service the next request: select it, move head, compute seek time.
        Returns the serviced DiskRequest (with seek_distance filled in).
        Returns None if queue empty.
        """
        target = self.select_next()
        if target is None:
            return None

        # Remove target from pending list
        # Find exact instance to remove correctly
        for i, r in enumerate(self.pending):
            if r is target:
                self.pending.pop(i)
                break

        start_head = self.current_head
        added_distance = 0

        if self.algorithm == "scan":
            if self.direction == 1:
                if target.cylinder >= start_head:
                    added_distance = target.cylinder - start_head
                    if added_distance > 0:
                        self.seek_trace.append((start_head, target.cylinder, added_distance))
                else:
                    # Bounce off upper boundary
                    boundary = self._cylinders - 1
                    dist1 = boundary - start_head
                    dist2 = boundary - target.cylinder
                    added_distance = dist1 + dist2
                    if dist1 > 0:
                        self.seek_trace.append((start_head, boundary, dist1))
                    if dist2 > 0:
                        self.seek_trace.append((boundary, target.cylinder, dist2))
                    self.direction = -1
            else:
                if target.cylinder <= start_head:
                    added_distance = start_head - target.cylinder
                    if added_distance > 0:
                        self.seek_trace.append((start_head, target.cylinder, added_distance))
                else:
                    # Bounce off lower boundary
                    boundary = 0
                    dist1 = start_head - boundary
                    dist2 = target.cylinder - boundary
                    added_distance = dist1 + dist2
                    if dist1 > 0:
                        self.seek_trace.append((start_head, boundary, dist1))
                    if dist2 > 0:
                        self.seek_trace.append((boundary, target.cylinder, dist2))
                    self.direction = 1

        elif self.algorithm == "c-scan":
            if target.cylinder >= start_head:
                added_distance = target.cylinder - start_head
                if added_distance > 0:
                    self.seek_trace.append((start_head, target.cylinder, added_distance))
            else:
                # Sweep to upper boundary, jump to 0, sweep to target
                boundary_upper = self._cylinders - 1
                boundary_lower = 0
                dist1 = boundary_upper - start_head
                dist_jump = boundary_upper - boundary_lower  # full disk sweep back
                dist2 = target.cylinder - boundary_lower

                added_distance = dist1 + dist_jump + dist2
                if dist1 > 0:
                    self.seek_trace.append((start_head, boundary_upper, dist1))
                self.seek_trace.append((boundary_upper, boundary_lower, dist_jump))
                if dist2 > 0:
                    self.seek_trace.append((boundary_lower, target.cylinder, dist2))

        elif self.algorithm in ("fcfs", "sstf", "look", "c-look"):
            added_distance = abs(target.cylinder - start_head)
            if added_distance > 0:
                self.seek_trace.append((start_head, target.cylinder, added_distance))

            # Update direction for LOOK if it reversed
            if self.algorithm == "look":
                if target.cylinder > start_head:
                    self.direction = 1
                elif target.cylinder < start_head:
                    self.direction = -1

        # Finalize state updates
        self.current_head = target.cylinder
        self.total_seek_distance += added_distance
        target.seek_distance = added_distance
        target.service_tick = self._current_tick

        # Cap seek trace to prevent unbounded growth during long simulations
        if len(self.seek_trace) > 200:
            self.seek_trace = self.seek_trace[-200:]

        return target

    def get_seek_trace(self) -> list[dict[str, Any]]:
        """Return list of {from_cylinder, to_cylinder, distance} dicts."""
        return [
            {"from_cylinder": f, "to_cylinder": t, "distance": d}
            for f, t, d in self.seek_trace
        ]

    def tick(self, current_tick: int) -> None:
        """Advance internal tick counter."""
        self._current_tick = current_tick
