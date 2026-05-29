# tests/conftest.py
# Phase: 10 — Testing & Validation
# Owner: QA Agent
"""
Pytest fixtures supporting deterministic multi-dimensional OS kernel verification suites.
Reference: OS101_AgentPlan_v2.md Section 15.3
"""
from pathlib import Path
import pytest
import yaml

from core.config import SimConfig
from modules.process.pcb import PCB, reset_pid_counter
from core.interrupt import InterruptController
from core.event_bus import EventBus
from core.kernel import Kernel


@pytest.fixture(autouse=True)
def reset_pids():
    """Ensure deterministic global PID boundaries before and after every executing test case."""
    reset_pid_counter()
    yield
    reset_pid_counter()


@pytest.fixture
def default_config() -> SimConfig:
    return SimConfig()


@pytest.fixture
def interrupt_controller() -> InterruptController:
    return InterruptController()


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def make_pcb():
    """Factory for creating test PCBs with deterministic PIDs."""
    reset_pid_counter()
    def _make(name="test", burst=10, priority=5, memory_pages=4, arrival_time=0) -> PCB:
        return PCB(
            name=name,
            burst_time=burst,
            priority=priority,
            memory_pages=memory_pages,
            arrival_time=arrival_time,
        )
    yield _make
    reset_pid_counter()


@pytest.fixture
def kernel_stub() -> Kernel:
    """Returns a pre-configured lightweight Kernel instance with max_ticks=10 and tick_rate_ms=1."""
    stub_cfg_path = Path("tests/stub_config.yaml")
    if not stub_cfg_path.exists():
        stub_cfg_path.parent.mkdir(parents=True, exist_ok=True)
        stub_cfg_path.write_text(yaml.dump({
            "clock": {"max_ticks": 10, "tick_rate_ms": 1},
            "cpu": {"cores": 1, "context_switch_cost": 1},
        }))
    
    k = Kernel(str(stub_cfg_path))
    return k
