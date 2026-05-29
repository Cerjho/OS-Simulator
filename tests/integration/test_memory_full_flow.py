# tests/integration/test_memory_full_flow.py
"""
Integration tests for memory management full flow.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import MemoryConfig
from core.interrupt import InterruptController
from modules.memory.allocator import MemoryAllocator
from modules.memory.paging import VirtualMemoryManager
from modules.memory.tlb import TLB
from modules.process.pcb import reset_pid_counter


@pytest.fixture(autouse=True)
def reset_pids():
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestMemoryFullFlow:

    def test_allocator_and_paging_together(self):
        """Allocator reserves frames; paging manages virtual-to-physical mapping."""
        allocator = MemoryAllocator(total_frames=16)
        cfg = MemoryConfig(total_frames=16, algorithm="lru", tlb_size=4)
        vmm = VirtualMemoryManager(cfg, InterruptController())

        # Allocate some frames for a process via allocator
        frames = allocator.allocate(pid=1, num_frames=4)
        assert frames is not None
        assert len(frames) == 4

        # Separately, demand-page into the VMM
        for page in range(4):
            vmm.handle_page_fault_direct(pid=1, page_num=page, tick=page + 1)

        snap = vmm.get_state_snapshot()
        assert snap["used_frames"] == 4
        assert snap["page_fault_count"] == 4

    def test_tlb_invalidation_on_context_switch(self):
        """TLB is fully flushed on context switch simulation."""
        tlb = TLB(size=4)
        tlb.insert(pid=1, virtual_page=0, frame=10)
        tlb.insert(pid=1, virtual_page=1, frame=11)
        assert tlb.current_entries == 2

        # Simulate context switch
        tlb.invalidate_all()
        assert tlb.current_entries == 0
        assert tlb.lookup(pid=1, virtual_page=0) is None

    def test_page_replacement_with_full_memory(self):
        """When all frames are used, page replacement must evict to load new pages."""
        cfg = MemoryConfig(total_frames=3, algorithm="lru", tlb_size=0)
        vmm = VirtualMemoryManager(cfg, InterruptController())

        # Fill all 3 frames
        for i in range(3):
            vmm.handle_page_fault_direct(pid=1, page_num=i, tick=i + 1)

        assert vmm.get_page_fault_count() == 3

        # Access page 3 — forces eviction
        frame = vmm.translate(pid=1, virtual_page=3, tick=5)
        assert frame is None  # Page fault
        vmm.handle_page_fault_direct(pid=1, page_num=3, tick=5)
        assert vmm.get_page_fault_count() == 4

        # Verify the new page is now accessible
        frame = vmm.translate(pid=1, virtual_page=3, tick=6)
        assert frame is not None

    def test_invariant_3_holds_after_multiple_operations(self):
        """INV-3: free + allocated == total after multiple alloc/dealloc cycles."""
        allocator = MemoryAllocator(total_frames=32)

        allocator.allocate(pid=1, num_frames=8)
        allocator.allocate(pid=2, num_frames=8)
        allocator.allocate(pid=3, num_frames=8)
        assert allocator.get_free_frame_count() + allocator.get_allocated_frame_count() == 32

        allocator.deallocate(pid=2)
        assert allocator.get_free_frame_count() + allocator.get_allocated_frame_count() == 32

        allocator.allocate(pid=4, num_frames=4)
        assert allocator.get_free_frame_count() + allocator.get_allocated_frame_count() == 32

    def test_compaction_consolidates_free_space(self):
        """Compaction moves all allocated blocks together and merges free space."""
        allocator = MemoryAllocator(total_frames=30)
        allocator.allocate(pid=1, num_frames=5)
        allocator.allocate(pid=2, num_frames=5)
        allocator.allocate(pid=3, num_frames=5)
        allocator.deallocate(pid=2)  # Creates hole in the middle

        frag_before = allocator.get_fragmentation()

        allocator.compact()
        frag_after = allocator.get_fragmentation()

        # After compaction: one big free block at the end
        blocks = allocator.visualize()
        free_blocks = [b for b in blocks if b["pid"] is None]
        assert len(free_blocks) == 1
        assert free_blocks[0]["size"] == 20  # 30 - 5 (pid1) - 5 (pid3) = 20 free
        assert frag_after["external_fragmentation"] <= frag_before["external_fragmentation"]
