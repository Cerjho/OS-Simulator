import pytest
import yaml

from core.kernel import Kernel
from modules.process.pcb import ProcessState


@pytest.mark.asyncio
async def test_kernel_admits_new_processes_on_tick(tmp_path):
    cfg_path = tmp_path / "sim.yaml"
    cfg_path.write_text(yaml.dump({
        "clock": {"tick_rate_ms": 1, "max_ticks": 50},
        "scheduler": {"algorithm": "round_robin", "time_quantum": 2, "preemptive": True, "aging_interval": 50},
        "memory": {"total_frames": 64, "algorithm": "lru", "page_size_kb": 4, "swap_enabled": True, "tlb_size": 16},
        "disk": {"scheduling": "sstf", "cylinders": 200, "initial_head": 53, "seek_time_per_track": 1},
        "processes": {"initial_load": 0, "auto_spawn": False},
    }))

    kernel = Kernel(str(cfg_path))
    await kernel._init_subsystems()

    kernel.inject_process({"name": "P1", "burst": 5, "priority": 3, "memory_pages": 2})
    kernel.inject_process({"name": "P2", "burst": 4, "priority": 4, "memory_pages": 2})
    assert len(kernel.process_manager.new_queue) == 2

    await kernel._on_tick(1)

    live_processes = kernel.process_manager.get_all_processes()
    assert live_processes
    assert all(p.state != ProcessState.NEW for p in live_processes)
    assert kernel.process_manager.running is not None
