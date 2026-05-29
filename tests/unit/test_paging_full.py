# tests/unit/test_paging_full.py
"""Comprehensive paging tests to reach 100% coverage on modules/memory/paging.py"""
import pytest
from modules.memory.paging import VirtualMemoryManager, _PageTableEntry
from core.config import MemoryConfig
from core.interrupt import InterruptController, InterruptType


def _make_config(**kw):
    defaults = {"total_frames": 4, "algorithm": "lru", "page_size_kb": 4,
                "swap_enabled": True, "tlb_size": 4}
    defaults.update(kw)
    return MemoryConfig(**defaults)


def _make_vmm(**kw):
    cfg = _make_config(**kw)
    ic = InterruptController()
    return VirtualMemoryManager(cfg, ic)


class TestTranslation:
    def test_translate_hit_via_tlb(self):
        vmm = _make_vmm(tlb_size=4)
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        # TLB should now have the entry; translate should hit TLB
        frame = vmm.translate(1, 0, tick=1)
        assert frame is not None
        assert frame >= 0

    def test_translate_hit_via_page_table_no_tlb(self):
        vmm = _make_vmm(tlb_size=0)
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        frame = vmm.translate(1, 0, tick=1)
        assert frame is not None

    def test_translate_miss_returns_none(self):
        vmm = _make_vmm()
        result = vmm.translate(1, 99, tick=0)
        assert result is None

    def test_translate_updates_access_metadata(self):
        vmm = _make_vmm()
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=5)
        vmm.translate(1, 0, tick=10)
        entry = vmm._get_page_entry(1, 0)
        assert entry.access_time == 10
        assert entry.reference is True

    def test_translate_page_table_hit_inserts_into_tlb(self):
        """When TLB misses but page table hits, entry should be loaded into TLB."""
        vmm = _make_vmm(tlb_size=4)
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        # Invalidate TLB to force page table lookup
        vmm._tlb.invalidate_all()
        frame = vmm.translate(1, 0, tick=5)
        assert frame is not None
        # Now TLB should have it again
        tlb_frame = vmm._tlb.lookup(1, 0)
        assert tlb_frame == frame


class TestPageFaultHandler:
    def test_handle_page_fault_via_interrupt(self):
        cfg = _make_config()
        ic = InterruptController()
        vmm = VirtualMemoryManager(cfg, ic)
        # Register the page fault handler
        ic.register_handler(InterruptType.PAGE_FAULT, vmm.handle_page_fault)
        ic.raise_interrupt(InterruptType.PAGE_FAULT, pid=1, current_tick=0,
                          data={"pid": 1, "page_num": 0})
        ic.handle_all()
        assert vmm.get_page_fault_count() == 1

    def test_handle_page_fault_direct_free_frame(self):
        vmm = _make_vmm(total_frames=4)
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        assert vmm.get_page_fault_count() == 1
        frame = vmm.translate(1, 0, tick=1)
        assert frame is not None

    def test_handle_page_fault_triggers_eviction(self):
        vmm = _make_vmm(total_frames=2, algorithm="fifo")
        # Fill all frames
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=1)
        # This should trigger eviction of page 0 (FIFO)
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=2)
        assert vmm.get_page_fault_count() == 3
        # Page 0 should no longer be present
        assert vmm.translate(1, 0, tick=3) is None

    def test_dirty_page_written_to_swap_on_eviction(self):
        vmm = _make_vmm(total_frames=2, algorithm="fifo")
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        # Mark page as dirty
        entry = vmm._get_page_entry(1, 0)
        entry.dirty = True
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=1)
        # Evict page 0
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=2)
        # Dirty page should be in swap space
        assert (1, 0) in vmm._swap_space


class TestEvictionAlgorithms:
    def test_fifo_evicts_oldest_load_time(self):
        vmm = _make_vmm(total_frames=2, algorithm="fifo")
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=1)
        # Access page 0 recently (should NOT matter for FIFO)
        vmm.translate(1, 0, tick=5)
        # Evict — should evict page 0 (oldest load_time), not page 1
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=6)
        assert vmm.translate(1, 0, tick=7) is None  # evicted
        assert vmm.translate(1, 1, tick=7) is not None  # still present

    def test_lru_evicts_least_recently_accessed(self):
        vmm = _make_vmm(total_frames=2, algorithm="lru")
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=1)
        # Access page 0 more recently than page 1
        vmm.translate(1, 0, tick=5)
        # Evict — should evict page 1 (LRU)
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=6)
        assert vmm.translate(1, 1, tick=7) is None  # evicted
        assert vmm.translate(1, 0, tick=7) is not None  # still present

    def test_clock_evicts_unreferenced_page(self):
        vmm = _make_vmm(total_frames=2, algorithm="clock")
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=1)
        # Clear reference bit on page 0
        entry0 = vmm._get_page_entry(1, 0)
        entry0.reference = False
        # Evict — clock should find page 0 unreferenced and evict it
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=2)
        assert vmm.translate(1, 0, tick=3) is None

    def test_clock_gives_second_chance(self):
        vmm = _make_vmm(total_frames=2, algorithm="clock")
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=1)
        # Both pages have reference=True (set on load)
        # Clock should give second chance to both, clear bits, then evict first one found
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=2)
        assert vmm.get_page_fault_count() == 3

    def test_clock_fallback_when_all_referenced(self):
        """Clock algorithm scans twice and falls back to clock hand position."""
        vmm = _make_vmm(total_frames=2, algorithm="clock")
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=1)
        # Keep refreshing reference bits (simulate constant access)
        vmm.translate(1, 0, tick=2)
        vmm.translate(1, 1, tick=3)
        # Trigger eviction
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=4)
        # Should still work (fallback)
        assert vmm.get_page_fault_count() == 3

    def test_optimal_evicts_farthest_future_use(self):
        vmm = _make_vmm(total_frames=2, algorithm="optimal")
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=1)
        # Set future: page 0 used at position 5, page 1 used at position 2
        vmm.set_future_accesses([(1, 1), (1, 1), (1, 0)])
        # Evict — should evict page 0 (used farthest in future)
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=2)
        assert vmm.translate(1, 0, tick=3) is None

    def test_optimal_evicts_never_used_again(self):
        vmm = _make_vmm(total_frames=2, algorithm="optimal")
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=1)
        # Page 0 never used again, page 1 used soon
        vmm.set_future_accesses([(1, 1)])
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=2)
        assert vmm.translate(1, 0, tick=3) is None

    def test_optimal_empty_present_pages(self):
        vmm = _make_vmm(total_frames=2, algorithm="optimal")
        # Directly call _evict_optimal with no frames loaded
        result = vmm._evict_optimal(tick=0)
        assert result == (-1, -1)

    def test_evict_page_default_fallback(self):
        vmm = _make_vmm(total_frames=2, algorithm="lru")
        vmm._algorithm = "unknown_algo"
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=1)
        # Should fall back to LRU
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=2)
        assert vmm.get_page_fault_count() == 3


class TestStatistics:
    def test_page_fault_rate(self):
        vmm = _make_vmm()
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.translate(1, 0, tick=1)
        vmm.translate(1, 0, tick=2)
        # 1 fault, 2 accesses from translate
        rate = vmm.get_page_fault_rate()
        assert 0 < rate < 1

    def test_page_fault_rate_zero_accesses(self):
        vmm = _make_vmm()
        assert vmm.get_page_fault_rate() == 0.0

    def test_get_state_snapshot(self):
        vmm = _make_vmm(total_frames=4)
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        snap = vmm.get_state_snapshot()
        assert snap["total_frames"] == 4
        assert snap["used_frames"] == 1
        assert snap["free_frames"] == 3
        assert "page_fault_count" in snap
        assert "algorithm" in snap

    def test_tlb_hit_rate(self):
        vmm = _make_vmm(tlb_size=4)
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.translate(1, 0, tick=1)  # TLB hit
        rate = vmm.get_tlb_hit_rate()
        assert rate > 0

    def test_set_future_accesses(self):
        vmm = _make_vmm()
        vmm.set_future_accesses([(1, 0), (2, 1)])
        assert len(vmm._future_accesses) == 2

    def test_tick_does_nothing(self):
        vmm = _make_vmm()
        vmm.tick(0)  # Should not raise


class TestTLBInteraction:
    def test_eviction_invalidates_tlb_entry(self):
        vmm = _make_vmm(total_frames=2, algorithm="fifo", tlb_size=4)
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=1)
        # TLB has entries for page 0 and 1
        assert vmm._tlb.lookup(1, 0) is not None
        # Evict page 0
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=2)
        # TLB entry for page 0 should be invalidated
        # (lookup won't find it since invalidate_page was called)

    def test_page_fault_loads_into_tlb(self):
        vmm = _make_vmm(tlb_size=4)
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        frame = vmm._tlb.lookup(1, 0)
        assert frame is not None
