# tests/scenarios/test_thrashing.py
"""
Scenario tests for memory thrashing detection.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import MemoryConfig
from core.interrupt import InterruptController
from modules.memory.paging import VirtualMemoryManager
from modules.process.pcb import reset_pid_counter


@pytest.fixture(autouse=True)
def reset_pids():
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestThrashingScenario:

    def test_thrashing_high_fault_rate_with_small_memory(self):
        """With very few frames and many pages, page fault rate should be extremely high."""
        cfg = MemoryConfig(total_frames=2, algorithm="fifo", tlb_size=0)
        vmm = VirtualMemoryManager(cfg, InterruptController())

        # Access 10 distinct pages with only 2 frames — constant eviction
        ref_string = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] * 3  # 30 accesses
        for t, page in enumerate(ref_string, start=1):
            frame = vmm.translate(pid=1, virtual_page=page, tick=t)
            if frame is None:
                vmm.handle_page_fault_direct(pid=1, page_num=page, tick=t)

        # With 2 frames and 10 pages cycling, fault rate should be very high
        snap = vmm.get_state_snapshot()
        assert snap["page_fault_count"] > 20  # Most accesses are faults
        fault_rate = snap["page_fault_count"] / snap["total_accesses"]
        assert fault_rate > 0.6, f"Expected thrashing fault rate > 0.6, got {fault_rate}"

    def test_adequate_frames_reduces_fault_rate(self):
        """With sufficient frames for the working set, fault rate drops dramatically."""
        cfg = MemoryConfig(total_frames=10, algorithm="lru", tlb_size=0)
        vmm = VirtualMemoryManager(cfg, InterruptController())

        # Same 10 pages, but now 10 frames — after warm-up, no more faults
        ref_string = list(range(10)) + list(range(10))  # 20 accesses
        for t, page in enumerate(ref_string, start=1):
            frame = vmm.translate(pid=1, virtual_page=page, tick=t)
            if frame is None:
                vmm.handle_page_fault_direct(pid=1, page_num=page, tick=t)

        # Only 10 faults (initial cold misses), then 10 hits
        assert vmm.get_page_fault_count() == 10
        fault_rate = vmm.get_page_fault_count() / 20
        assert fault_rate == 0.5  # Exactly 50% (cold misses only)

    def test_lru_outperforms_fifo_on_locality_workload(self):
        """LRU should produce fewer faults than FIFO on a workload with temporal locality."""
        ref_string = [1, 2, 3, 1, 2, 4, 1, 2, 3, 4, 1, 2]

        # FIFO
        cfg_fifo = MemoryConfig(total_frames=3, algorithm="fifo", tlb_size=0)
        vmm_fifo = VirtualMemoryManager(cfg_fifo, InterruptController())
        for t, page in enumerate(ref_string, start=1):
            frame = vmm_fifo.translate(pid=1, virtual_page=page, tick=t)
            if frame is None:
                vmm_fifo.handle_page_fault_direct(pid=1, page_num=page, tick=t)

        # LRU
        cfg_lru = MemoryConfig(total_frames=3, algorithm="lru", tlb_size=0)
        vmm_lru = VirtualMemoryManager(cfg_lru, InterruptController())
        for t, page in enumerate(ref_string, start=1):
            frame = vmm_lru.translate(pid=1, virtual_page=page, tick=t)
            if frame is None:
                vmm_lru.handle_page_fault_direct(pid=1, page_num=page, tick=t)

        lru_faults = vmm_lru.get_page_fault_count()
        fifo_faults = vmm_fifo.get_page_fault_count()
        # LRU should produce fewer or equal faults with locality
        assert lru_faults <= fifo_faults, f"LRU({lru_faults}) > FIFO({fifo_faults})"

    def test_working_set_transition_causes_fault_spike(self):
        """Transitioning to a new working set causes a spike in page faults."""
        cfg = MemoryConfig(total_frames=4, algorithm="lru", tlb_size=0)
        vmm = VirtualMemoryManager(cfg, InterruptController())

        # Phase 1: working set {0,1,2,3} — 4 cold faults, then hits
        phase1 = [0, 1, 2, 3, 0, 1, 2, 3, 0, 1]
        for t, page in enumerate(phase1, start=1):
            frame = vmm.translate(pid=1, virtual_page=page, tick=t)
            if frame is None:
                vmm.handle_page_fault_direct(pid=1, page_num=page, tick=t)

        faults_after_phase1 = vmm.get_page_fault_count()
        assert faults_after_phase1 == 4  # Only initial cold misses

        # Phase 2: working set shifts to {4,5,6,7} — 4 new faults
        phase2 = [4, 5, 6, 7, 4, 5, 6, 7]
        base_t = len(phase1) + 1
        for i, page in enumerate(phase2):
            t = base_t + i
            frame = vmm.translate(pid=1, virtual_page=page, tick=t)
            if frame is None:
                vmm.handle_page_fault_direct(pid=1, page_num=page, tick=t)

        faults_after_phase2 = vmm.get_page_fault_count()
        new_faults = faults_after_phase2 - faults_after_phase1
        assert new_faults == 4  # Exactly 4 new cold misses for the new working set
