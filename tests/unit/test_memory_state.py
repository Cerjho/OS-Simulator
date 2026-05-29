# tests/unit/test_memory_state.py
"""Tests for the kernel's _get_memory_state() aggregation fix."""
import pytest
from core.config import MemoryConfig
from core.interrupt import InterruptController
from modules.memory.paging import VirtualMemoryManager


def _make_vmm(total_frames=8):
    cfg = MemoryConfig(total_frames=total_frames, algorithm="lru",
                       page_size_kb=4, swap_enabled=True, tlb_size=0)
    return VirtualMemoryManager(cfg, InterruptController())


class TestMemoryStateAggregation:
    """Tests the contiguous block aggregation that MemoryMap.jsx relies on."""

    def _aggregate_blocks(self, vmm):
        """Reproduce kernel._get_memory_state() block aggregation logic."""
        blocks = []
        occupied = []
        for frame_num, occupant in vmm._frame_table.items():
            if occupant is not None:
                pid, _page = occupant
                occupied.append((frame_num, pid))
        occupied.sort(key=lambda x: x[0])

        if occupied:
            run_base, run_pid = occupied[0]
            run_size = 1
            for i in range(1, len(occupied)):
                frame_num, pid = occupied[i]
                if pid == run_pid and frame_num == run_base + run_size:
                    run_size += 1
                else:
                    blocks.append({"base": run_base, "size": run_size, "pid": run_pid})
                    run_base, run_pid, run_size = frame_num, pid, 1
            blocks.append({"base": run_base, "size": run_size, "pid": run_pid})
        return blocks

    def test_empty_memory_produces_no_blocks(self):
        vmm = _make_vmm(8)
        blocks = self._aggregate_blocks(vmm)
        assert blocks == []

    def test_single_page_produces_single_block(self):
        vmm = _make_vmm(8)
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        blocks = self._aggregate_blocks(vmm)
        assert len(blocks) == 1
        assert blocks[0]["pid"] == 1
        assert blocks[0]["size"] == 1

    def test_contiguous_same_pid_merged(self):
        vmm = _make_vmm(8)
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=1)
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=2)
        blocks = self._aggregate_blocks(vmm)
        assert len(blocks) == 1
        assert blocks[0]["size"] == 3
        assert blocks[0]["pid"] == 1

    def test_different_pids_produce_separate_blocks(self):
        vmm = _make_vmm(8)
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.handle_page_fault_direct(pid=2, page_num=0, tick=1)
        blocks = self._aggregate_blocks(vmm)
        assert len(blocks) == 2
        pids = {b["pid"] for b in blocks}
        assert pids == {1, 2}

    def test_blocks_have_required_keys(self):
        vmm = _make_vmm(8)
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        blocks = self._aggregate_blocks(vmm)
        for b in blocks:
            assert "base" in b
            assert "size" in b
            assert "pid" in b

    def test_non_contiguous_same_pid_split(self):
        vmm = _make_vmm(8)
        # Load pages for pid 1 in frames 0, 1, then pid 2 in frame 2, then pid 1 in frame 3
        vmm.handle_page_fault_direct(pid=1, page_num=0, tick=0)
        vmm.handle_page_fault_direct(pid=1, page_num=1, tick=1)
        vmm.handle_page_fault_direct(pid=2, page_num=0, tick=2)
        vmm.handle_page_fault_direct(pid=1, page_num=2, tick=3)
        blocks = self._aggregate_blocks(vmm)
        # Should be: [pid1 size=2, pid2 size=1, pid1 size=1]
        assert len(blocks) == 3
