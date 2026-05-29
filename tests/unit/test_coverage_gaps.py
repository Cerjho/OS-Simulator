# tests/unit/test_coverage_gaps.py
"""Targeted tests for remaining coverage gaps across all algorithm modules."""
import pytest
from modules.process.pcb import PCB, ProcessState
from modules.process.scheduler import (
    FCFS, SJF, PriorityScheduler, RoundRobin, MLFQ, create_scheduler
)
from modules.process.queue_manager import QueueManager
from modules.io.disk import DiskScheduler
from modules.memory.paging import VirtualMemoryManager
from modules.memory.allocator import MemoryAllocator
from modules.sync.deadlock import DeadlockDetector
from core.config import SchedulerConfig, DiskConfig, MemoryConfig, DeadlockConfig
from core.interrupt import InterruptController
from core.event_bus import EventBus


def _sched_cfg(**kw):
    d = {"algorithm": "fcfs", "time_quantum": 4, "preemptive": True, "aging_interval": 5}
    d.update(kw)
    return SchedulerConfig(**d)


def _make_pcb(name, burst, arrival=0, priority=5):
    return PCB(name=name, burst_time=burst, priority=priority,
               memory_pages=1, arrival_time=arrival)


def _make_qm():
    return QueueManager(InterruptController(), EventBus())


# ── Scheduler select_next returning None on empty queues ──

class TestSchedulerEmptyQueues:
    def test_fcfs_select_next_empty(self):
        assert FCFS(_sched_cfg()).select_next([], 0) is None

    def test_sjf_select_next_empty(self):
        assert SJF(_sched_cfg(algorithm="sjf")).select_next([], 0) is None

    def test_priority_select_next_empty(self):
        assert PriorityScheduler(_sched_cfg(algorithm="priority")).select_next([], 0) is None

    def test_rr_select_next_empty(self):
        assert RoundRobin(_sched_cfg(algorithm="round_robin")).select_next([], 0) is None

    def test_mlfq_select_next_empty(self):
        assert MLFQ(_sched_cfg(algorithm="mlfq")).select_next([], 0) is None

    def test_mlfq_select_next_all_levels_empty(self):
        """MLFQ returns None when all level buckets are empty."""
        mlfq = MLFQ(_sched_cfg(algorithm="mlfq"))
        # Pass processes not at any standard level (edge case)
        assert mlfq.select_next([], 0) is None


class TestMLFQAgingRunning:
    def test_mlfq_aging_promotes_running_at_level_1(self):
        """Running process at level 1 gets promoted to level 0 after aging."""
        mlfq = MLFQ(_sched_cfg(algorithm="mlfq", aging_interval=5))
        qm = _make_qm()
        p1 = _make_pcb("A", 20, arrival=0)
        qm.new_queue.append(p1)
        qm.admit(p1)
        qm.dispatch(p1, tick=0)
        p1.mlfq_queue_level = 1
        # Tick at aging boundary — should promote from 1 to 0
        mlfq.tick(5, qm)
        assert p1.mlfq_queue_level == 0

    def test_mlfq_aging_running_at_level_0_stays(self):
        """Running process already at level 0 stays at level 0 (guard: > 0)."""
        mlfq = MLFQ(_sched_cfg(algorithm="mlfq", aging_interval=5))
        qm = _make_qm()
        p1 = _make_pcb("A", 20, arrival=0)
        qm.new_queue.append(p1)
        qm.admit(p1)
        qm.dispatch(p1, tick=0)
        p1.mlfq_queue_level = 0
        mlfq.tick(5, qm)
        assert p1.mlfq_queue_level == 0


class TestPriorityPreemptAndDispatch:
    def test_priority_tick_preempts_and_dispatches(self):
        ps = PriorityScheduler(_sched_cfg(algorithm="priority"))
        qm = _make_qm()
        p1 = _make_pcb("A", 10, priority=5)
        p2 = _make_pcb("B", 10, priority=1)
        qm.new_queue.append(p1)
        qm.new_queue.append(p2)
        qm.admit(p1)
        qm.admit(p2)
        qm.dispatch(p1, tick=0)
        # p2 has higher priority (lower number) → should preempt
        ps.tick(1, qm)
        assert qm.running is p2


# ── Disk: SCAN descending reversal fallback, LOOK fallback ──

class TestDiskFallbacks:
    def test_scan_descending_all_behind(self):
        ds = DiskScheduler(DiskConfig(cylinders=200, initial_head=100,
                                      scheduling="scan", seek_time_per_track=1))
        ds.direction = -1
        ds.add_request(50, pid=1, request_id="r1")
        r = ds.select_next()
        assert r.cylinder == 50

    def test_scan_descending_reversal(self):
        """SCAN descending with no behind requests reverses direction."""
        ds = DiskScheduler(DiskConfig(cylinders=200, initial_head=10,
                                      scheduling="scan", seek_time_per_track=1))
        ds.direction = -1
        ds.add_request(150, pid=1, request_id="r1")
        r = ds.select_next()
        assert r.cylinder == 150

    def test_scan_fallback(self):
        """SCAN fallback returns pending[0] when no behind/ahead categorization works."""
        ds = DiskScheduler(DiskConfig(cylinders=200, initial_head=53,
                                      scheduling="scan", seek_time_per_track=1))
        ds.add_request(53, pid=1, request_id="r1")
        r = ds.select_next()
        assert r is not None

    def test_look_fallback(self):
        """LOOK fallback returns pending[0]."""
        ds = DiskScheduler(DiskConfig(cylinders=200, initial_head=53,
                                      scheduling="look", seek_time_per_track=1))
        ds.add_request(53, pid=1, request_id="r1")
        r = ds.select_next()
        assert r is not None

    def test_generic_fallback_unknown_algo(self):
        """Unknown algorithm falls back to pending[0]."""
        ds = DiskScheduler(DiskConfig(cylinders=200, initial_head=53,
                                      scheduling="fcfs", seek_time_per_track=1))
        ds.algorithm = "nonexistent"
        ds.add_request(100, pid=1, request_id="r1")
        r = ds.select_next()
        assert r is not None

    def test_scan_descending_service_reversal(self):
        """SCAN descending service_next reversal code path."""
        ds = DiskScheduler(DiskConfig(cylinders=200, initial_head=50,
                                      scheduling="scan", seek_time_per_track=1))
        ds.direction = -1
        ds.add_request(100, pid=1, request_id="r1")
        r = ds.service_next()
        assert r is not None
        assert ds.direction == 1  # Reversed


# ── Paging: clock fallback, evict dispatching ──

class TestPagingClockFallback:
    def test_clock_fallback_returns_valid(self):
        """Clock algorithm fallback when occupant at clock_hand is None."""
        cfg = MemoryConfig(total_frames=4, algorithm="clock", page_size_kb=4,
                          swap_enabled=True, tlb_size=0)
        vmm = VirtualMemoryManager(cfg, InterruptController())
        # Load only 2 pages but have 4 frames (some empty)
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=1)
        # Point clock hand past occupied frames
        vmm._clock_hand = 0
        # Clear reference bits to ensure eviction
        for pg in [0, 1]:
            entry = vmm._get_page_entry(1, pg)
            if entry:
                entry.reference = False
        result = vmm.evict_page(tick=2)
        assert result != (-1, -1)

    def test_evict_page_dispatches_clock(self):
        cfg = MemoryConfig(total_frames=2, algorithm="clock", page_size_kb=4,
                          swap_enabled=True, tlb_size=0)
        vmm = VirtualMemoryManager(cfg, InterruptController())
        vmm.handle_page_fault_direct(1, 0, 0)
        vmm.handle_page_fault_direct(1, 1, 1)
        vmm._get_page_entry(1, 0).reference = False
        result = vmm.evict_page(2)
        assert result[0] == 1

    def test_evict_page_dispatches_optimal(self):
        cfg = MemoryConfig(total_frames=2, algorithm="optimal", page_size_kb=4,
                          swap_enabled=True, tlb_size=0)
        vmm = VirtualMemoryManager(cfg, InterruptController())
        vmm.handle_page_fault_direct(1, 0, 0)
        vmm.handle_page_fault_direct(1, 1, 1)
        vmm.set_future_accesses([(1, 1)])
        result = vmm.evict_page(2)
        assert result == (1, 0)


# ── Deadlock: event_bus publish exception suppression ──

class TestDeadlockEventSuppression:
    def test_detect_suppresses_broken_event_bus(self):
        """Event bus publish exception should be caught silently."""
        class BrokenEventBus:
            def publish(self, *args, **kwargs):
                raise RuntimeError("Bus broken")

        dd = DeadlockDetector(
            DeadlockConfig(detection_interval=10, recovery_strategy="terminate_youngest"),
            BrokenEventBus()
        )
        dd.update("allocate", 1, "R1")
        dd.update("allocate", 2, "R2")
        dd.update("request", 1, "R2")
        dd.update("request", 2, "R1")
        # Should not raise despite broken event bus
        cycles = dd.detect()
        assert len(cycles) > 0

    def test_recover_suppresses_broken_event_bus(self):
        class BrokenEventBus:
            def publish(self, *args, **kwargs):
                raise RuntimeError("Bus broken")

        dd = DeadlockDetector(
            DeadlockConfig(detection_interval=10, recovery_strategy="terminate_youngest"),
            BrokenEventBus()
        )
        dd.update("allocate", 1, "R1")
        dd.update("allocate", 2, "R2")
        dd.update("request", 1, "R2")
        dd.update("request", 2, "R1")
        cycles = dd.detect()
        affected = dd.recover(cycles, "terminate_youngest")
        assert len(affected) > 0


# ── Deadlock Banker's: hardcoded bypass path ──

class TestBankersEdgeCases:
    def test_bankers_trivially_safe_empty_needs(self):
        """Empty allocation and need matrices are trivially safe (all processes finish immediately)."""
        dd = DeadlockDetector(
            DeadlockConfig(detection_interval=10, recovery_strategy="terminate_youngest"),
            EventBus()
        )
        available = {"A": 3, "B": 3, "C": 0}
        allocation = {0: {}, 1: {}, 2: {}, 3: {}, 4: {}}
        need = {0: {}, 1: {}, 2: {}, 3: {}, 4: {}}
        assert dd.is_safe_state(available, allocation, need) is True
