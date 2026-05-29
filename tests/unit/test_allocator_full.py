# tests/unit/test_allocator_full.py
"""Comprehensive allocator tests for 100% coverage."""
import pytest
from modules.memory.allocator import MemoryAllocator


class TestSetAlgorithm:
    def test_set_valid(self):
        a = MemoryAllocator(64)
        for algo in ["first_fit", "best_fit", "worst_fit"]:
            a.set_algorithm(algo)

    def test_set_invalid_raises(self):
        with pytest.raises(ValueError):
            MemoryAllocator(64).set_algorithm("random")


class TestAllocate:
    def test_zero_returns_none(self):
        assert MemoryAllocator(10).allocate(1, 0) is None

    def test_exact_fit(self):
        a = MemoryAllocator(10)
        assert a.allocate(1, 10) == list(range(10))
        assert a.get_free_frame_count() == 0

    def test_partial_fit(self):
        a = MemoryAllocator(10)
        assert a.allocate(1, 4) == [0, 1, 2, 3]

    def test_insufficient_returns_none(self):
        a = MemoryAllocator(10)
        a.allocate(1, 8)
        assert a.allocate(2, 5) is None


class TestBestFit:
    def test_selects_smallest_adequate(self):
        a = MemoryAllocator(20)
        a.set_algorithm("best_fit")
        a.allocate(1, 5); a.allocate(2, 3); a.allocate(3, 7)
        a.deallocate(2); a.deallocate(3)
        assert a.allocate(4, 3) == [5, 6, 7]

    def test_none_if_no_fit(self):
        a = MemoryAllocator(5)
        a.set_algorithm("best_fit")
        a.allocate(1, 5)
        assert a.allocate(2, 1) is None


class TestWorstFit:
    def test_selects_largest(self):
        a = MemoryAllocator(20)
        a.set_algorithm("worst_fit")
        a.allocate(1, 5); a.allocate(2, 3); a.allocate(3, 2)
        a.deallocate(2); a.deallocate(3)
        # After coalescing: [0-4]=P1, [5-19]=free(15)
        # Worst fit picks the largest block = [5-19]
        frames = a.allocate(4, 2)
        assert frames is not None
        assert len(frames) == 2

    def test_none_if_no_fit(self):
        a = MemoryAllocator(5)
        a.set_algorithm("worst_fit")
        a.allocate(1, 5)
        assert a.allocate(2, 1) is None


class TestDeallocateAndCoalesce:
    def test_coalesces(self):
        a = MemoryAllocator(15)
        a.allocate(1, 5); a.allocate(2, 5); a.allocate(3, 5)
        a.deallocate(1); a.deallocate(2)
        assert a.allocate(4, 10) == list(range(10))

    def test_nonexistent_pid(self):
        assert MemoryAllocator(10).deallocate(999) == []


class TestFragmentation:
    def test_external_frag(self):
        a = MemoryAllocator(20)
        a.allocate(1, 5); a.allocate(2, 5); a.allocate(3, 5)
        a.deallocate(1); a.deallocate(3)
        f = a.get_fragmentation()
        assert f["external_fragmentation"] > 0

    def test_no_frag_full(self):
        a = MemoryAllocator(5)
        a.allocate(1, 5)
        f = a.get_fragmentation()
        assert f["external_fragmentation"] == 0.0


class TestCompact:
    def test_defragments(self):
        a = MemoryAllocator(15)
        a.allocate(1, 3); a.allocate(2, 4); a.allocate(3, 3)
        a.deallocate(2)
        a.compact()
        assert a.allocate(4, 9) is not None


class TestSnapshot:
    def test_visualize(self):
        a = MemoryAllocator(10)
        a.allocate(1, 4)
        b = a.visualize()
        assert any(x["pid"] == 1 for x in b)

    def test_get_state_snapshot(self):
        a = MemoryAllocator(10)
        a.allocate(1, 3)
        s = a.get_state_snapshot()
        assert s["total_frames"] == 10
        assert s["allocated_frames"] == 3
