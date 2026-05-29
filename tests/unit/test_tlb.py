# tests/unit/test_tlb.py
"""
Unit tests for tlb.
Reference: OS101_AgentPlan_v2.md Section 15
"""
import pytest
from modules.memory.tlb import TLB
from modules.process.pcb import reset_pid_counter


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure PIDs are deterministic across tests."""
    reset_pid_counter()
    yield
    reset_pid_counter()


class TestTLB:

    def test_lookup_miss_on_empty(self):
        # Arrange
        tlb = TLB(size=4)
        # Act
        result = tlb.lookup(pid=1, virtual_page=0)
        # Assert
        assert result is None
        assert tlb.miss_count == 1

    def test_lookup_hit_after_insert(self):
        # Arrange
        tlb = TLB(size=4)
        tlb.insert(pid=1, virtual_page=0, frame=10)
        # Act
        result = tlb.lookup(pid=1, virtual_page=0)
        # Assert
        assert result == 10
        assert tlb.hit_count == 1

    def test_lru_eviction_on_overflow(self):
        # Arrange
        tlb = TLB(size=2)
        tlb.insert(pid=1, virtual_page=0, frame=10)  # LRU
        tlb.insert(pid=1, virtual_page=1, frame=11)  # MRU
        # Act — inserting a 3rd entry should evict page 0 (LRU)
        tlb.insert(pid=1, virtual_page=2, frame=12)
        # Assert
        assert tlb.lookup(pid=1, virtual_page=0) is None  # evicted
        assert tlb.lookup(pid=1, virtual_page=1) == 11
        assert tlb.lookup(pid=1, virtual_page=2) == 12

    def test_invalidate_removes_pid_entries(self):
        # Arrange
        tlb = TLB(size=4)
        tlb.insert(pid=1, virtual_page=0, frame=10)
        tlb.insert(pid=1, virtual_page=1, frame=11)
        tlb.insert(pid=2, virtual_page=0, frame=20)
        # Act
        tlb.invalidate(pid=1)
        # Assert
        assert tlb.lookup(pid=1, virtual_page=0) is None
        assert tlb.lookup(pid=1, virtual_page=1) is None
        assert tlb.lookup(pid=2, virtual_page=0) == 20

    def test_invalidate_all_clears_cache(self):
        # Arrange
        tlb = TLB(size=4)
        tlb.insert(pid=1, virtual_page=0, frame=10)
        tlb.insert(pid=2, virtual_page=0, frame=20)
        # Act
        tlb.invalidate_all()
        # Assert
        assert tlb.current_entries == 0

    def test_hit_rate_calculation(self):
        # Arrange
        tlb = TLB(size=4)
        tlb.insert(pid=1, virtual_page=0, frame=10)
        # Act
        tlb.lookup(pid=1, virtual_page=0)  # hit
        tlb.lookup(pid=1, virtual_page=0)  # hit
        tlb.lookup(pid=1, virtual_page=1)  # miss
        # Assert
        assert tlb.hit_rate == pytest.approx(2.0 / 3.0, abs=0.01)

    def test_hit_rate_zero_with_no_accesses(self):
        # Arrange & Act
        tlb = TLB(size=4)
        # Assert
        assert tlb.hit_rate == 0.0

    def test_insert_updates_existing_entry(self):
        # Arrange
        tlb = TLB(size=4)
        tlb.insert(pid=1, virtual_page=0, frame=10)
        # Act — update mapping to a different frame
        tlb.insert(pid=1, virtual_page=0, frame=99)
        # Assert
        assert tlb.lookup(pid=1, virtual_page=0) == 99
        assert tlb.current_entries == 1

    def test_invalidate_page_removes_single_entry(self):
        # Arrange
        tlb = TLB(size=4)
        tlb.insert(pid=1, virtual_page=0, frame=10)
        tlb.insert(pid=1, virtual_page=1, frame=11)
        # Act
        tlb.invalidate_page(pid=1, virtual_page=0)
        # Assert
        assert tlb.lookup(pid=1, virtual_page=0) is None
        assert tlb.lookup(pid=1, virtual_page=1) == 11
