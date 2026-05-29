# tests/unit/test_tlb_full.py
"""Tests for full TLB coverage — reset_stats path."""
from modules.memory.tlb import TLB


class TestTLBResetStats:
    def test_reset_stats_clears_counters(self):
        tlb = TLB(size=4)
        tlb.insert(1, 0, 10)
        tlb.lookup(1, 0)   # hit
        tlb.lookup(1, 99)  # miss
        assert tlb.hit_count > 0
        assert tlb.miss_count > 0
        tlb.reset_stats()
        assert tlb.hit_count == 0
        assert tlb.miss_count == 0

    def test_current_entries(self):
        tlb = TLB(size=4)
        assert tlb.current_entries == 0
        tlb.insert(1, 0, 10)
        assert tlb.current_entries == 1
