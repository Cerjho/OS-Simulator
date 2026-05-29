# tests/unit/test_paging.py
"""
Unit tests for paging.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from core.config import MemoryConfig
from core.interrupt import InterruptController
from modules.memory.paging import VirtualMemoryManager
from modules.process.pcb import reset_pid_counter


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestVirtualMemoryManager:

    def test_lru_reference_string_9_faults(self):
        # Arrange - Textbook string: 7 0 1 2 0 3 0 4 2 3 0 3 with 3 frames
        cfg = MemoryConfig(algorithm="lru", total_frames=3, tlb_size=0)
        vmm = VirtualMemoryManager(cfg, InterruptController())
        ref_string = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3]
        # Act
        for t, page in enumerate(ref_string, start=1):
            frame = vmm.translate(pid=1, virtual_page=page, tick=t)
            if frame is None:
                vmm.handle_page_fault_direct(pid=1, page_num=page, tick=t)
        # Assert
        assert vmm.get_page_fault_count() == 9

    def test_fifo_reference_string_10_faults(self):
        # Arrange - Textbook string: 7 0 1 2 0 3 0 4 2 3 0 3 with 3 frames
        cfg = MemoryConfig(algorithm="fifo", total_frames=3, tlb_size=0)
        vmm = VirtualMemoryManager(cfg, InterruptController())
        ref_string = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3]
        # Act
        for t, page in enumerate(ref_string, start=1):
            frame = vmm.translate(pid=1, virtual_page=page, tick=t)
            if frame is None:
                vmm.handle_page_fault_direct(pid=1, page_num=page, tick=t)
        # Assert
        assert vmm.get_page_fault_count() == 10

    def test_translate_returns_none_on_page_fault(self):
        # Arrange
        cfg = MemoryConfig(total_frames=3)
        vmm = VirtualMemoryManager(cfg, InterruptController())
        # Act
        frame = vmm.translate(pid=1, virtual_page=5, tick=1)
        # Assert
        assert frame is None

    def test_tlb_hit_after_warm_up(self):
        # Arrange
        cfg = MemoryConfig(total_frames=4, tlb_size=4)
        vmm = VirtualMemoryManager(cfg, InterruptController())
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=1) # Loads to memory and TLB
        # Act
        frame = vmm.translate(pid=1, virtual_page=2, tick=2)
        # Assert
        assert frame is not None
        assert vmm.get_tlb_hit_rate() > 0.0

    def test_dirty_bit_set_on_write_access(self):
        # Arrange
        cfg = MemoryConfig(total_frames=3)
        vmm = VirtualMemoryManager(cfg, InterruptController())
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=1)
        # Act
        entry = vmm._get_page_entry(pid=1, virtual_page=2)
        assert entry is not None
        entry.dirty = True
        # Assert
        assert entry.dirty is True

    def test_present_bit_set_after_page_load(self):
        # Arrange
        cfg = MemoryConfig(total_frames=3)
        vmm = VirtualMemoryManager(cfg, InterruptController())
        # Act
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=1)
        # Assert
        entry = vmm._get_page_entry(pid=1, virtual_page=2)
        assert entry is not None
        assert entry.present is True

    def test_eviction_writes_dirty_page_to_swap(self):
        # Arrange
        cfg = MemoryConfig(algorithm="fifo", total_frames=1)
        vmm = VirtualMemoryManager(cfg, InterruptController())
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=1) # frame 0 holds page 0
        entry = vmm._get_page_entry(pid=1, virtual_page=0)
        entry.dirty = True
        # Act
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=2) # Evicts page 0
        # Assert
        assert (1, 0) in vmm._swap_space

    def test_eviction_skips_clean_page_swap_write(self):
        # Arrange
        cfg = MemoryConfig(algorithm="fifo", total_frames=1)
        vmm = VirtualMemoryManager(cfg, InterruptController())
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=1) # clean page
        # Act
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=2)
        # Assert
        assert (1, 0) not in vmm._swap_space

    def test_page_fault_count_increments(self):
        # Arrange
        cfg = MemoryConfig(total_frames=3)
        vmm = VirtualMemoryManager(cfg, InterruptController())
        # Act
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=1)
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=2)
        # Assert
        assert vmm.get_page_fault_count() == 2

    def test_free_frames_decrease_after_allocation(self):
        # Arrange
        cfg = MemoryConfig(total_frames=4)
        vmm = VirtualMemoryManager(cfg, InterruptController())
        # Act
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=1)
        # Assert
        snap = vmm.get_state_snapshot()
        assert snap["free_frames"] == 3
