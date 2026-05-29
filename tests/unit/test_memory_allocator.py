# tests/unit/test_memory_allocator.py
"""
Unit tests for memory_allocator.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from modules.memory.allocator import MemoryAllocator
from modules.process.pcb import reset_pid_counter


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestMemoryAllocator:

    def test_initial_all_frames_free(self):
        # Arrange & Act
        allocator = MemoryAllocator(total_frames=64)
        # Assert
        assert allocator.get_free_frame_count() == 64
        assert allocator.get_allocated_frame_count() == 0

    def test_allocate_reduces_free_count(self):
        # Arrange
        allocator = MemoryAllocator(total_frames=64)
        # Act
        frames = allocator.allocate(pid=1, num_frames=10)
        # Assert
        assert frames == list(range(10))
        assert allocator.get_free_frame_count() == 54
        assert allocator.get_allocated_frame_count() == 10

    def test_deallocate_restores_free_count(self):
        # Arrange
        allocator = MemoryAllocator(total_frames=64)
        allocator.allocate(pid=1, num_frames=10)
        # Act
        freed = allocator.deallocate(pid=1)
        # Assert
        assert len(freed) == 10
        assert allocator.get_free_frame_count() == 64
        assert allocator.get_allocated_frame_count() == 0

    def test_invariant_free_plus_used_equals_total(self):
        # Arrange
        allocator = MemoryAllocator(total_frames=64)
        # Act & Assert
        allocator.allocate(pid=1, num_frames=10)
        assert allocator.get_free_frame_count() + allocator.get_allocated_frame_count() == 64
        allocator.allocate(pid=2, num_frames=20)
        assert allocator.get_free_frame_count() + allocator.get_allocated_frame_count() == 64
        allocator.deallocate(pid=1)
        assert allocator.get_free_frame_count() + allocator.get_allocated_frame_count() == 64

    def test_allocate_returns_none_when_insufficient(self):
        # Arrange
        allocator = MemoryAllocator(total_frames=10)
        # Act
        res = allocator.allocate(pid=1, num_frames=20)
        # Assert
        assert res is None

    def test_first_fit_selects_first_available_hole(self):
        # Arrange
        allocator = MemoryAllocator(total_frames=30)
        allocator.allocate(pid=1, num_frames=10) # 0..9
        allocator.allocate(pid=2, num_frames=10) # 10..19
        allocator.deallocate(pid=1) # 0..9 free hole
        # Act
        res = allocator.allocate(pid=3, num_frames=5)
        # Assert
        assert res == list(range(5))

    def test_coalesce_adjacent_free_blocks(self):
        # Arrange
        allocator = MemoryAllocator(total_frames=30)
        allocator.allocate(pid=1, num_frames=10)
        allocator.allocate(pid=2, num_frames=10)
        allocator.allocate(pid=3, num_frames=10)
        # Act
        allocator.deallocate(pid=1)
        allocator.deallocate(pid=2) # Should merge with 1's free block
        # Assert
        blocks = allocator.visualize()
        free_blocks = [b for b in blocks if b["pid"] is None]
        assert len(free_blocks) == 1
        assert free_blocks[0]["size"] == 20

    def test_fragmentation_ratio_between_0_and_1(self):
        # Arrange
        allocator = MemoryAllocator(total_frames=64)
        allocator.allocate(pid=1, num_frames=10)
        allocator.allocate(pid=2, num_frames=10)
        allocator.deallocate(pid=1)
        # Act
        frag = allocator.get_fragmentation()
        # Assert
        ext = frag["external_fragmentation"] / 100.0
        assert 0.0 <= ext <= 1.0
