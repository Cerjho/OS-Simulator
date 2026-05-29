# modules/sync/deadlock.py
# Phase: 7 — Synchronization & Deadlock
# Owner: Sync Agent
"""
Resource Allocation Graph (RAG) Deadlock Detection and Banker's Algorithm Safe State verification.
Full implementation spec: OS101_AgentPlan_v2.md Section 12
"""
from __future__ import annotations
import collections
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import DeadlockConfig
    from core.event_bus import EventBus


class DeadlockDetector:
    """
    Tracks resource allocation state to detect cycles and verify allocation safety.

    State tracked:
      _allocations: Mapping from PID to list of held resource IDs.
      _requests: Mapping from PID to pending requested resource ID.
    """

    def __init__(self, config: DeadlockConfig, event_bus: EventBus) -> None:
        self.config: DeadlockConfig = config
        self._event_bus: EventBus = event_bus

        self._allocations: dict[int, list[str]] = collections.defaultdict(list)
        self._requests: dict[int, str | None] = collections.defaultdict(lambda: None)

        self._detected: bool = False
        self._cached_cycles: list[list[int]] = []
        self._last_check_tick: int = 0
        self._current_tick: int = 0

    def update(self, event_type: str, pid: int, resource_id: str) -> None:
        """
        Update the Resource Allocation Graph (RAG) state based on operational events.
        Supported event_types: 'allocate', 'request', 'release'.
        """
        if event_type == "allocate":
            if resource_id not in self._allocations[pid]:
                self._allocations[pid].append(resource_id)
            # Clear request if satisfied
            if self._requests[pid] == resource_id:
                self._requests[pid] = None

        elif event_type == "request":
            self._requests[pid] = resource_id

        elif event_type == "release":
            if resource_id in self._allocations[pid]:
                self._allocations[pid].remove(resource_id)
            if self._requests[pid] == resource_id:
                self._requests[pid] = None

    def detect(self) -> list[list[int]]:
        """
        Execute depth-first search cycle detection over the directed Wait-For graph.
        Returns a list of isolated simple cycles (each represented as a list of PIDs).
        Returns empty list if the system is deadlock-free.
        """
        self._last_check_tick = self._current_tick

        # Map resource IDs to list of current owner PIDs
        owner_map: dict[str, list[int]] = collections.defaultdict(list)
        for pid, res_list in self._allocations.items():
            for r in res_list:
                owner_map[r].append(pid)

        # Build Wait-For adjacency matrix mapping PID to target PIDs
        adj: dict[int, list[int]] = collections.defaultdict(list)
        all_pids: set[int] = set(self._allocations.keys()) | set(self._requests.keys())

        for pid, req_res in self._requests.items():
            if req_res is not None and req_res in owner_map:
                for target_pid in owner_map[req_res]:
                    adj[pid].append(target_pid)

        cycles: list[list[int]] = []
        canonical_cycles: set[tuple[int, ...]] = set()

        # Non-recursive elementary cycle discovery using stack traversal
        for start_node in sorted(all_pids):
            stack = [(start_node, [start_node], {start_node})]
            while stack:
                curr, path, visited = stack.pop()
                for neighbor in adj[curr]:
                    if neighbor == start_node:
                        if len(path) > 1:
                            # Normalize canonical cycle rotation to filter duplicates
                            min_idx = path.index(min(path))
                            canon = tuple(path[min_idx:] + path[:min_idx])
                            if canon not in canonical_cycles:
                                canonical_cycles.add(canon)
                                cycles.append(list(path))
                    elif neighbor not in visited:
                        stack.append((neighbor, path + [neighbor], visited | {neighbor}))

        self._detected = len(cycles) > 0
        self._cached_cycles = cycles

        if self._detected and hasattr(self._event_bus, "publish"):
            try:
                self._event_bus.publish(
                    "DEADLOCK_DETECTED",
                    {"cycles": cycles},
                    tick=self._current_tick,
                    source="deadlock_detector",
                )
            except Exception:
                pass

        return cycles

    def is_safe_state(
        self,
        available: dict[str, int],
        allocation: dict[int, dict[str, int]],
        need: dict[int, dict[str, int]],
    ) -> bool:
        """
        Verify allocation safety using Banker's Algorithm.
        Evaluates if a safe execution sequence exists preventing potential resource starvation.
        """
        # Graceful handling for edge case: no processes means trivially safe
        if not allocation and not need:
            return True

        work = dict(available)
        all_pids = set(allocation.keys()) | set(need.keys())
        finish = {pid: False for pid in all_pids}

        while True:
            progress = False
            for pid in sorted(all_pids):
                if not finish[pid]:
                    p_need = need.get(pid, {})
                    # Verify if all requested resources satisfy need bounds
                    if all(p_need.get(r, 0) <= work.get(r, 0) for r in p_need):
                        finish[pid] = True
                        p_alloc = allocation.get(pid, {})
                        for r, count in p_alloc.items():
                            work[r] = work.get(r, 0) + count
                        progress = True
                        break
            if not progress:
                break

        return all(finish.values())

    def recover(self, cycles: list[list[int]], strategy: str) -> list[int]:
        """
        Execute recovery strategy over identified deadlock cycles.
        Supported strategies: 'terminate_youngest', 'terminate_lowest', 'resource_preempt'.
        Returns list of affected PIDs.
        """
        affected_pids: set[int] = set()

        for cycle in cycles:
            if not cycle:
                continue

            target_pid = cycle[0]
            if strategy == "terminate_youngest":
                # Sequential allocation assigns younger processes higher numerical PIDs
                target_pid = max(cycle)

            elif strategy == "terminate_lowest":
                # Lowest priority = select process with smallest PID (oldest, least critical)
                target_pid = min(cycle)

            elif strategy == "resource_preempt":
                # Preempt resources from the youngest process but don't fully terminate
                target_pid = max(cycle)

            affected_pids.add(target_pid)

            # Preempt and clear internal allocations to break cycle wait-for dependencies
            if target_pid in self._allocations:
                self._allocations[target_pid].clear()
            if target_pid in self._requests:
                self._requests[target_pid] = None

        unique_affected = sorted(affected_pids)
        self._detected = False
        self._cached_cycles.clear()

        if unique_affected and hasattr(self._event_bus, "publish"):
            try:
                self._event_bus.publish(
                    "DEADLOCK_RECOVERED",
                    {"affected_pids": unique_affected, "strategy": strategy},
                    tick=self._current_tick,
                    source="deadlock_detector",
                )
            except Exception:
                pass

        return unique_affected

    def get_state_snapshot(self) -> dict[str, Any]:
        """Serializable telemetry snapshot detailing current deadlock metrics."""
        # FE-BUG-04/05 fix: Filter out empty allocations and null requests
        # to prevent orphan nodes in dashboard RAG graph
        clean_allocs = {pid: res_list for pid, res_list in self._allocations.items() if res_list}
        clean_reqs = {pid: res_id for pid, res_id in self._requests.items() if res_id is not None}
        return {
            "detected": self._detected,
            "cycles": self._cached_cycles,
            "last_check_tick": self._last_check_tick,
            "allocations": clean_allocs,
            "requests": clean_reqs,
        }

    def tick(self, current_tick: int) -> None:
        """Advance internal simulation clock tick."""
        self._current_tick = current_tick
